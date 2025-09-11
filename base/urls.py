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
    path('api/test-clear/<int:fixture_id>/', test_clear_counter),
    
    path('api/add-to-counter/', CreateUpdateCounter.as_view(), name='add_to_counter'),
    path('api/add-multi-to-counter/', CreateMultiCounter.as_view(), name='add-multi-to-counter'),

    path('api/check-status/', ReturnServerStatus.as_view(), name='check-status'),
    
]