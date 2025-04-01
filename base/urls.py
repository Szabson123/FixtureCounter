from django.urls import path
from .views import *

urlpatterns = [
    path('', home_view),
    path('add-to-counter/', CreateUpdateCounter.as_view(), name='add_to_counter'),
    path('all_counters/', display_machine_data, name='all_counters'),
    path('clear_counter/<int:fixture_id>/', clear_main_counter, name='clear_main_counter'),
    path('fixtures/json/', fixture_data_json, name='fixture_data_json'),
]