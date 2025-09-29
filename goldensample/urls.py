from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'goldens', GoldenSampleAdminView, basename='golden-manage')
router.register(r'variant', VariantListView, basename='variant-manage')
router.register(r'(?P<variant_id>\d+)/goldens', GoldenSampleVariantList, basename='golden-variant')
router.register(r'mastersamples/client-name', ClientNameViewSet, basename='client-name')
router.register(r'mastersamples/type-name', TypeNameViewSet, basename='type-name')
router.register(r'mastersamples/process-name', ProcessNameViewSet, basename='process-name')
router.register(r'mastersamples/departament-name', DepartmentViewSet, basename='departament-name')
router.register(r'mastersamples/code-smd-name', CodeSmdViewSet, basename='code-smd-name')
router.register(r'mastersamples/end-code', EndCodeViewSet, basename='end-code')


urlpatterns = [
    path('add-golden/', GoldenSampleCreateView.as_view(), name='create_golden_sample'),
    
    path('check/', GoldenSampleCheckView.as_view(), name='check_golden_sample'),
    path('type/', GoldenSampleTypeCheckView.as_view(), name='golden_sample_type_check'),
    
    path('bulk_add/', GoldenSampleBulkUploadView.as_view(), name='bulk_add'),
    
    path('check_bin/', GoldenSampleBinChecker.as_view(), name='check_bin'),
    path('add_bin/', GoldenSampleBinAdder.as_view(), name='add-bin'),

    path('add-event-sn/', AddEventSn.as_view(), name='add-event-sn'),
    path('check-event-sn/', CheckEventSn.as_view(), name='add-event-sn'),

    path("mastersamples/", MasterSampleListView.as_view(), name="mastersample-list"),
]

urlpatterns += router.urls