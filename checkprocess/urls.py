from django.urls import path
from .views import ProcessProductViewSet, ProductViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'product', ProductViewSet, basename='product')
router.register(r'(?P<product_id>\d+)/process', ProcessProductViewSet, basename='process-product')


urlpatterns = [

]

urlpatterns += router.urls