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
    path("mastersamples/", MasterSampleListView.as_view(), name="mastersample-list"),
    path("mastersamples/create/", MasterSampleCreateView.as_view(), name='mastersample-create'),
    path("mastersamples/<int:pk>/", MasterSampleRetrieveUpdateView.as_view(), name='mastersample-retrive'),

    path("machine_validation/", MachineTimeStampView.as_view(), name='machine_validation'),
    
    path("mastersample-check/", MasterSampleCheckView.as_view(), name='master-check-SPEA'),
    path("mastersample-type/", MasterSampleTypeCheck.as_view(), name="master-type-SPEA"),

    path('mastersample/fwk/check/', CheckGoldensFWK.as_view(), name="master-type-FWK"),
    path('mastersample/fwk/set-invalid/', ClearSamplesResult.as_view(), name='fwk-invaldiate'),
    path('mastersample/fwk/set-valid/', SetGoldensTrue.as_view(), name='valid-machine'),

    path('variant/', MasterSampleProjectNames.as_view(), name='engineer-view')
]

urlpatterns += router.urls