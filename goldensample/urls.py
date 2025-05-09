from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import ProductFamilyViewSet, VariantCodeViewSet, GoldenSampleCodeViewSet, VerifyGoldenSamplesView

router = DefaultRouter()
router.register(r'families', ProductFamilyViewSet, basename='family')
router.register(r'variants', VariantCodeViewSet, basename='variant')
router.register(r'goldens', GoldenSampleCodeViewSet, basename='golden')

urlpatterns = [
    path('', include(router.urls)),
    
    path('verify/', VerifyGoldenSamplesView.as_view(), name='verify-goldens'),
]