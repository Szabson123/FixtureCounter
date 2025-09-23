from django.urls import path
from .views import (ProductViewSet, ProductProcessViewSet, ProductObjectViewSet,
                    ProductObjectProcessViewSet, BulkProductObjectCreateAndAddMotherView, ProductObjectProcessLogViewSet,
                    PlaceViewSet, ProductMoveView, AppKillStatusView, GraphImportView, ProductStartNewProduction,
                    ContinueProduction, ScrapProduct, BulkProductObjectCreateView, ListGroupsStatuses, SubProductsCounter)

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='products')
router.register(r'(?P<product_id>\d+)/product-processes', ProductProcessViewSet, basename='products-process')
router.register(r'(?P<product_id>\d+)/(?P<process_uuid>[0-9a-f-]+)/product-objects', ProductObjectViewSet, basename='product-objects')
router.register(r'(?P<process_id>[^/]+)/place', PlaceViewSet, basename='place')
router.register(r'(?P<product_object_id>\d+)/product-object-processes', ProductObjectProcessViewSet, basename='product-object-processes')
router.register(r'product-object-process-logs', ProductObjectProcessLogViewSet, basename='product-object-process-logs')


urlpatterns = [
    path('product-object/move/<uuid:process_uuid>/', ProductMoveView.as_view(), name='product-move'),
    path('start-new-prod/<uuid:process_uuid>/', ProductStartNewProduction.as_view(), name='start-prouduction'),
    path('continue-prod/<uuid:process_uuid>/', ContinueProduction.as_view(), name='continue-prouduction'),
    path('trash-obj/<uuid:process_uuid>/', ScrapProduct.as_view(), name='scrap-product'),
    
    path('<int:product_id>/<uuid:process_uuid>/bulk-create/', BulkProductObjectCreateView.as_view(), name='bulk-product-object-create'),
    path('<int:product_id>/<uuid:process_uuid>/bulk-create-to-mother/', BulkProductObjectCreateAndAddMotherView.as_view(), name='bulk-product-object-create-to-mother'),
    
    path('kill-app/', AppKillStatusView.as_view(), name='kill-app'),
    
    path('<int:product_id>/graph-import/', GraphImportView.as_view(), name='graph-import'),
    path('get-statuses-groups/', ListGroupsStatuses.as_view(), name='list-group-statuses'),
    path('counter-products/', SubProductsCounter.as_view(), name='couter-products')
]

urlpatterns += router.urls