from django.urls import path
from .views import ProductViewSet, ProductProcessViewSet, ProductObjectViewSet, ProductObjectProcessViewSet, ProductObjectProcessLogViewSet, PlaceViewSet, ProductMoveView, AppKillStatusView, ProductReceiveView, QuickAddToMotherView, GraphImportView
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='products')
router.register(r'(?P<product_id>\d+)/product-processes', ProductProcessViewSet, basename='products-process')
router.register(r'(?P<product_id>\d+)/product-objects', ProductObjectViewSet, basename='product-objects')
router.register(r'(?P<process_id>[^/]+)/place', PlaceViewSet, basename='place')
router.register(r'(?P<product_object_id>\d+)/product-object-processes', ProductObjectProcessViewSet, basename='product-object-processes')
router.register(r'(?P<product_object_process_id>\d+)/product-object-process-logs', ProductObjectProcessLogViewSet, basename='product-object-process-logs')


urlpatterns = [
    path("quick-add-child/", QuickAddToMotherView.as_view(), name="quick-add-child"),
    
    path('product-object/move/<int:process_id>/', ProductMoveView.as_view(), name='product-move'),
    path('product-object/receive/<int:process_id>/', ProductReceiveView.as_view(), name='product-receive'),
    path('kill-app/', AppKillStatusView.as_view(), name='kill-app'),
    
    path('<int:product_id>/graph-import/', GraphImportView.as_view(), name='graph-import'),
]

urlpatterns += router.urls