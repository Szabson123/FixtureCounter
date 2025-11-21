from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.db.models import F, OuterRef, Subquery
from django.utils import timezone
from django.db.models import F, ExpressionWrapper, FloatField, Subquery, OuterRef
from django.db.models.functions import Cast
from django.conf import settings
from django.core.cache import cache
from django_eventstream import send_event
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework import viewsets, status, generics
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import permission_classes, api_view, authentication_classes
from rest_framework.authentication import SessionAuthentication

from .models import Fixture, CounterSumFromLastMaint, CounterHistory, FullCounter, Machine, MachineCondition
from .serializers import UpdateCreateCounter, FixtureSerializer, MachineSerializer, FullInfoFixtureSerializer


@method_decorator(csrf_exempt, name='dispatch')
class ClearCounterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, fixture_id):
        fixture = get_object_or_404(Fixture, id=fixture_id)
        input_password = request.data.get('password', '')

        if input_password != settings.CLEAR_COUNTER_PASSWORD:
            return Response({'error': 'Nieprawidłowe hasło'}, status=status.HTTP_400_BAD_REQUEST)

        if fixture.counter_last_maint and fixture.counter_last_maint.counter != 0:
            CounterHistory.objects.create(
                fixture=fixture,
                counter=fixture.counter_last_maint.counter
            )
            fixture.counter_last_maint.counter = 0
            fixture.counter_last_maint.save()
            return Response({'status': 'Licznik wyczyszczony'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Brak licznika do wyzerowania'}, status=status.HTTP_400_BAD_REQUEST)


class UpdateCounter(GenericAPIView):
    serializer_class = UpdateCreateCounter

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fixture_name = serializer.validated_data['fixture_name']

        cache_key = f"fixture_request_{fixture_name}"
        last_request_time = cache.get(cache_key)

        if last_request_time and (timezone.now() - last_request_time).seconds < 10:
            return Response(
                {"returnCodeDescription": "Request for this fixture was sent too recently. Please wait.",
                 "returnCode": 429},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        cache.set(cache_key, timezone.now(), timeout=10)

        fixture, created = Fixture.objects.get_or_create(name=fixture_name)
        if created:
            counter = CounterSumFromLastMaint.objects.create(counter=1)
            all_counter = FullCounter.objects.create(counter=1)
            fixture.counter_last_maint = counter
            fixture.counter_all = all_counter
            fixture.save()
            message = "Fixture created in FixtureCycleCounter"
        else:
            fixture.counter_last_maint.counter += 1
            fixture.counter_all.counter += 1
            fixture.counter_last_maint.save()
            fixture.counter_all.save()
            message = "Fixture counter updated in FixtureCycleCounter"

        send_event('fixture-updates', 'message', {
            "fixture_name": fixture.name,
            "message": message,
            "timestamp": timezone.now().isoformat(),
        })

        return Response(
                {"returnCodeDescription": message,
                 "returnCode": 200},
                status=status.HTTP_200_OK
            )

class GetInfoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FullInfoFixtureSerializer
    ordering_fields = [
        'name',
        'counter_all_value',
        'counter_last_maint_value',
        'last_maint_date',
        'limit_procent',
    ]
    search_fields = ['name']

    def get_queryset(self):
        last_maint_date_subquery = CounterHistory.objects.filter(
            fixture=OuterRef('pk')
        ).order_by('-date').values('date')[:1]

        return Fixture.objects.annotate(
            counter_all_value=F('counter_all__counter'),
            counter_last_maint_value=F('counter_last_maint__counter'),
            last_maint_date=Subquery(last_maint_date_subquery),
            limit_procent=ExpressionWrapper(
                Cast(F('counter_last_maint__counter'), FloatField()) * 100.0 / F('cycles_limit'),
                output_field=FloatField()
            ),
        )

    
class MachineViewSet(viewsets.ModelViewSet):
    serializer_class = MachineSerializer
    queryset = Machine.objects.all()


class ReturnServerStatus(APIView):
    def get(self, request):
        return Response("Server is working", status=status.HTTP_200_OK)
    

class CheckExceedCyclesLimit(GenericAPIView):
    serializer_class = UpdateCreateCounter

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fixture_name = serializer.validated_data['fixture_name']

        try:
            machine = Fixture.objects.get(name=fixture_name)
        except:
            return Response({"error": "Fixture doesnt exist"})

        if machine.counter_last_maint.counter >= machine.cycles_limit:
            return Response({"fail": "Limit exceeded stop machine"})
        else:
            return Response({"pass": "Can produce"})
