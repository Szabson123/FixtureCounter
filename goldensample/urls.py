from django.urls import path
from .views import GoldenSampleCreateView, GoldenSampleCheckView, GoldenSampleTypeCheckView, GoldenSampleAdminView, VariantListView, GoldenSampleBulkUploadView, GoldenSampleVariantList
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'goldens', GoldenSampleAdminView, basename='golden-manage')
router.register(r'variant', VariantListView, basename='variant-manage')
router.register(r'(?P<variant_id>\d+)/goldens', GoldenSampleVariantList, basename='golden-variant')


urlpatterns = [
    path('add-golden/', GoldenSampleCreateView.as_view(), name='create_golden_sample'),
    
    path('check/', GoldenSampleCheckView.as_view(), name='check_golden_sample'),
    path('type/', GoldenSampleTypeCheckView.as_view(), name='golden_sample_type_check'),
    
    path('bulk_add/', GoldenSampleBulkUploadView.as_view(), name='bulk_add'),
]

urlpatterns += router.urls