from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.db.models import F, OuterRef, Subquery
from django.utils import timezone

from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from .models import Fixture, Counter, CounterSumFromLastMaint, CounterHistory, FullCounter
from .serializers import CounterSerializer, CounterFromLastMaintSerializer, FixtureSerializer
from .forms import PasswordForm


class CreateUpdateCounter(generics.CreateAPIView):
    queryset = Fixture.objects.all()
    serializer_class = FixtureSerializer
    
    def create(self, request, *args, **kwargs):
        fixture_name = request.data.get('name')
        
        
        if fixture_name:
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

            return Response(
                {"returnCodeDescription": message,
                "returnCode": 2137},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"returnCodeDescription": "You didn't pass the name",
                "returnCode": 1488},
                status=status.HTTP_400_BAD_REQUEST
            )



def display_machine_data(request):
    latest_counterhistory_subquery = CounterHistory.objects.filter(
        fixture=OuterRef('pk')
    ).order_by('-date').values('date')[:1]

    fixtures = (
        Fixture.objects.all()
        .select_related('counter_last_maint', 'counter_all')
        .annotate(last_counterhistory_date=Subquery(latest_counterhistory_subquery))
    )

    sort_param = request.GET.get('sort')

    valid_sorts = {
        'name': 'name',
        '-name': '-name',
        'all_counter': 'counter_all__counter',
        '-all_counter': '-counter_all__counter',
        'last_maint': 'counter_last_maint__counter',
        '-last_maint': '-counter_last_maint__counter',
        'last_history': 'last_counterhistory_date',
        '-last_history': '-last_counterhistory_date',
    }

    if sort_param in valid_sorts:
        fixtures = fixtures.order_by(valid_sorts[sort_param])
    else:
        fixtures = fixtures.order_by('-counter_last_maint__counter')

    fixture_data = []
    for fixture in fixtures:
        last_maint_value = fixture.counter_last_maint.counter if fixture.counter_last_maint else None
        all_value = fixture.counter_all.counter if fixture.counter_all else None

        last_date_obj = fixture.last_counterhistory_date

        if last_date_obj is not None:
            last_date_formatted = last_date_obj.strftime("%Y-%m-%d")
        else:
            last_date_formatted = "Nigdy nie wykonano przeglądu" 

        fixture_data.append({
            'name': fixture.name,
            'last_maint_counter': last_maint_value,
            'all_counter': all_value,
            'last_counterhistory_date': last_date_formatted,
            'clear_counter_url': reverse('clear_main_counter', args=[fixture.id]),
        })

    form = PasswordForm()
    return render(request, 'base/machine_data.html', {
        'fixture_data': fixture_data,
        'form': form,
        'sort_param': sort_param,
    })


def clear_main_counter(request, fixture_id):
    fixture = get_object_or_404(Fixture, id=fixture_id)
    fixtures = Fixture.objects.all()

    if request.method == 'POST':
        form = PasswordForm(request.POST)
        if form.is_valid():
            input_password = form.cleaned_data['password']
            if input_password == settings.CLEAR_COUNTER_PASSWORD:
                if fixture.counter_last_maint and fixture.counter_last_maint.counter != 0:
                    CounterHistory.objects.create(
                        fixture=fixture,
                        counter=fixture.counter_last_maint.counter
                    )
                    fixture.counter_last_maint.counter = 0
                    fixture.counter_last_maint.save()
                else:
                    print("Brak licznika do wyzerowania")
            else:
                print("Nieprawidłowe hasło")
                return redirect('all_counters')
            
        return redirect('all_counters')
    else:
        form = PasswordForm()

    return render(request, 'base/machine_data.html', {
        'fixture_data': fixtures,
        'form': form
    })

# AJAX
def fixture_data_json(request):
    sort_param = request.GET.get('sort')

    latest_history_subquery = CounterHistory.objects.filter(
        fixture=OuterRef('pk')
    ).order_by('-date').values('date')[:1]

    fixtures = (
        Fixture.objects.all()
        .select_related('counter_last_maint', 'counter_all')
        .annotate(last_history_date=Subquery(latest_history_subquery))
    )

    valid_sorts = {
        'name': 'name',
        '-name': '-name',
        'all_counter': 'counter_all__counter',
        '-all_counter': '-counter_all__counter',
        'last_maint': 'counter_last_maint__counter',
        '-last_maint': '-counter_last_maint__counter',
        'last_history': 'last_history_date',
        '-last_history': '-last_history_date',
    }
    
    if sort_param in valid_sorts:
        fixtures = fixtures.order_by(valid_sorts[sort_param])
    else:
        fixtures = fixtures.order_by('name')
    
    fixture_data = []
    for fixture in fixtures:
        last_maint_value = fixture.counter_last_maint.counter if fixture.counter_last_maint else None
        all_value = fixture.counter_all.counter if fixture.counter_all else None
        
        last_history_value = fixture.last_history_date
        
        if last_history_value is not None:
            last_history_formatted = last_history_value.strftime("%Y-%m-%d")
        else:
            last_history_formatted = None

        fixture_data.append({
            'id': fixture.id,
            'name': fixture.name,
            'last_maint_counter': last_maint_value,
            'all_counter': all_value,
            'last_counterhistory_date': last_history_formatted,
            'clear_counter_url': reverse('clear_main_counter', args=[fixture.id]),
        })

    return JsonResponse({'fixture_data': fixture_data})