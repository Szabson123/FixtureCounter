from django.urls import path, include
from .views import *
from rest_framework.routers import DefaultRouter
from django_eventstream import urls as eventstream_urls

router = DefaultRouter()
router.register(r'machine', MachineViewSet, basename='machine')
router.register(r'get_info', GetInfoViewSet, basename='get_info')

urlpatterns = [
    path('', home_view),
    
    path('api/machine/', include(router.urls)),
    path('api/clear-counter/<int:fixture_id>/', ClearCounterAPIView.as_view(), name='api_clear_counter'),
    path('api/events/', include(eventstream_urls)),
    path('api/test-cors/', test_cors),
    
    path('add-to-counter/', CreateUpdateCounter.as_view(), name='add_to_counter'),
    path('add-multi-to-counter/', CreateMultiCounter.as_view(), name='add-multi-to-counter'),
    
    path('all_counters/', display_machine_data, name='all_counters'),
    path('clear_counter/<int:fixture_id>/', clear_main_counter, name='clear_main_counter'),
    path('fixtures/json/', fixture_data_json, name='fixture_data_json'),
]