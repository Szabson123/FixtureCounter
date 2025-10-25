from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'mastersamples/client-name', ClientNameViewSet, basename='client-name')
router.register(r'mastersamples/type-name', TypeNameViewSet, basename='type-name')
router.register(r'mastersamples/process-name', ProcessNameViewSet, basename='process-name')
router.register(r'mastersamples/departament-name', DepartmentViewSet, basename='departament-name')
router.register(r'mastersamples/code-smd-name', CodeSmdViewSet, basename='code-smd-name')
router.register(r'mastersamples/end-code', EndCodeViewSet, basename='end-code')


urlpatterns = [
    path('check/', GoldenSampleCheckView.as_view(), name='check_golden_sample'),
    path('type/', GoldenSampleTypeCheckView.as_view(), name='golden_sample_type_check'),
    
    path('check_bin/', GoldenSampleBinChecker.as_view(), name='check_bin'),
    path('add_bin/', GoldenSampleBinAdder.as_view(), name='add-bin'),

    path('add-event-sn/', AddEventSn.as_view(), name='add-event-sn'),
    path('check-event-sn/', CheckEventSn.as_view(), name='add-event-sn'),

    path("mastersamples/", MasterSampleListView.as_view(), name="mastersample-list"),
    path("mastersamples/create/", MasterSampleCreateView.as_view(), name='mastersample-create'),
    path("mastersamples/<int:pk>/", MasterSampleRetrieveUpdateView.as_view(), name='mastersample-retrive'),

    path("machine_validation/", MachineTimeStampView.as_view(), name='machine_validation'),
    path("mastersample-check/", MasterSampleCheckView.as_view(), name='master-check'),
    path("mastersample-type/", MasterSampleTypeCheck.as_view(), name="master-type")

]

urlpatterns += router.urls