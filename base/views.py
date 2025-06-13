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

from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import permission_classes, api_view, authentication_classes

from .models import Fixture, CounterSumFromLastMaint, CounterHistory, FullCounter, Machine, MachineCondition
from .serializers import FixtureSerializer, MachineSerializer, FullInfoFixtureSerializer
from django.views.decorators.csrf import csrf_exempt

from goldensample.models import GroupVariantCode, VariantCode, MapSample, GoldenSample
from rest_framework.authentication import SessionAuthentication

from datetime import timedelta
from django.db import models

class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return

def home_view(request):
    return redirect('/all_counters/')

from django.http import JsonResponse


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def test_clear_counter(request, fixture_id):
    return Response({'status': f'Fixture {fixture_id} zresetowany'}, status=status.HTTP_200_OK)

def test_cors(request):
    return JsonResponse({"message": "CORS działa poprawnie"})


@method_decorator(csrf_exempt, name='dispatch')
class ClearCounterAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
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


class CreateMultiCounter(generics.CreateAPIView):
    queryset = Fixture.objects.all()
    serializer_class = FixtureSerializer
    
    def create(self, request, *args, **kwargs):
        fixture_name = request.data.get('name')
        how_much_counter = int(request.data.get('number', 0))
        
        if not fixture_name:
            return Response(
                {"returnCodeDescription": "Fixture name is required",
                 "returnCode": "MISSING_NAME"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if how_much_counter <= 0:
            return Response(
                {"returnCodeDescription": "Number must be positive",
                 "returnCode": "INVALID_NUMBER"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cache_key = f"fixture_request_{fixture_name}"
        last_request_time = cache.get(cache_key)
        
        if last_request_time and (timezone.now() - last_request_time).seconds < 10:
            return Response(
                {"returnCodeDescription": "Request for this fixture was sent too recently. Please wait.",
                 "returnCode": "429"},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        cache.set(cache_key, timezone.now(), timeout=10)
        
        try:
            fixture = Fixture.objects.get(name=fixture_name)
        except Fixture.DoesNotExist:
            return Response(
                {"returnCodeDescription": "Fixture not found",
                 "returnCode": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND
            )

        fixture.counter_last_maint.counter += how_much_counter
        fixture.counter_all.counter += how_much_counter
        fixture.counter_last_maint.save()
        fixture.counter_all.save()
        
        return Response(
            {
                "returnCodeDescription": f"Counters updated successfully. Added {how_much_counter}",
                "returnCode": 200,
            },
            status=status.HTTP_200_OK
        )


class CreateUpdateCounter(generics.CreateAPIView):
    queryset = Fixture.objects.all()
    serializer_class = FixtureSerializer
    
    authentication_classes = [CsrfExemptSessionAuthentication]

    def create(self, request, *args, **kwargs):
        fixture_name = request.data.get('name')
        
        sn = request.data.get('serial_number')

        if not fixture_name:
            return Response(
                {"returnCodeDescription": "You didn't pass the name",
                 "returnCode": 1488},
                status=status.HTTP_400_BAD_REQUEST
            )

        cache_key = f"fixture_request_{fixture_name}"
        last_request_time = cache.get(cache_key)

        if last_request_time and (timezone.now() - last_request_time).seconds < 10:
            send_event('fixture-updates', 'message', {
                "fixture_name": fixture_name,
                "message": "Too soon – request ignored",
                "timestamp": timezone.now().isoformat(),
            })
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
        
        
        if sn and len(sn) >= 13:
            group_code = str(sn[12:]).strip()
            reason_8 = "Minęło więcej niż 8 godzin od ostatniego testu wzorców"
            reason_map = "Nie ma mapowania"
            reason_group = "Nie znaleziono żadnej grupy"
            reason = None
            machine_block = False

            try:
                check_sn = GoldenSample.objects.get(golden_code=sn)
                return Response({
                    "returnCodeDescription": message,
                    "returnCode": 200,
                    "machineBlock": False,
                    "reason": None,
                }, status=status.HTTP_200_OK)

            except GoldenSample.DoesNotExist:
                inner_variant = group_code
                group = GroupVariantCode.objects.filter(name=group_code).first()

                if not group:
                    map_entry = MapSample.objects.filter(
                        models.Q(i_output=group_code) | models.Q(i_input=group_code)
                    ).first()

                    if not map_entry:
                        machine_block = True
                        reason = reason_map
                        return Response({
                            "returnCodeDescription": message,
                            "returnCode": 403,
                            "machineBlock": machine_block,
                            "reason": reason,
                        }, status=status.HTTP_200_OK)

                    alt_code = (
                        map_entry.i_input if map_entry.i_output == group_code else map_entry.i_output
                    )
                    group = GroupVariantCode.objects.filter(name=alt_code).first()

                    if group:
                        inner_variant = alt_code
                    else:
                        machine_block = True
                        reason = reason_group
                        return Response({
                            "returnCodeDescription": message,
                            "returnCode": 403,
                            "machineBlock": machine_block,
                            "reason": reason,
                        }, status=status.HTTP_200_OK)

                if group.last_time_tested:
                    time_diff = timezone.now() - group.last_time_tested
                    if time_diff > timedelta(hours=8):
                        machine_block = True
                        reason = reason_8

            return Response({
                "returnCodeDescription": message,
                "returnCode": 200,
                "machineBlock": machine_block,
                "reason": reason,
            }, status=status.HTTP_200_OK)

        else:
            return Response(
                {"returnCodeDescription": message,
                "returnCode": 200},
                status=status.HTTP_200_OK
            )

class GetInfoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FullInfoFixtureSerializer

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

    ordering_fields = [
        'name',
        'counter_all_value',
        'counter_last_maint_value',
        'last_maint_date',
        'limit_procent',
    ]
    search_fields = ['name']
    
    
class MachineViewSet(viewsets.ModelViewSet):
    serializer_class = MachineSerializer
    queryset = Machine.objects.all()
