from django.urls import path
from .views import (ProductViewSet, ProductProcessViewSet, ProductObjectViewSet,
                    ProductObjectProcessViewSet, BulkProductObjectCreateAndAddMotherView, ProductObjectProcessLogViewSet,
                    PlaceViewSet, ProductMoveView, AppKillStatusView, GraphImportView, ProductStartNewProduction,
                    ContinueProduction, ScrapProduct, BulkProductObjectCreateView, ListGroupsStatuses, SubProductsCounter, ProductMoveListView,
                    RetoolingView, StencilStartNewProd, LogFromMistakeData, ProductProcessList, PlaceInGroupAdmin, UnifiedLogsViewSet, ProductObjectAdminViewSet,
                    ProductObjectAdminViewSetProcessHelper, ProductObjectAdminViewSetPlaceHelper, GroupUpdateStatus)

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='products')
router.register(r'(?P<product_id>\d+)/product-processes', ProductProcessViewSet, basename='products-process')
router.register(r'(?P<product_id>\d+)/(?P<process_uuid>[0-9a-f-]+)/product-objects', ProductObjectViewSet, basename='product-objects')
router.register(r'(?P<process_id>[^/]+)/place', PlaceViewSet, basename='place')
router.register(r'(?P<product_object_id>\d+)/product-object-processes', ProductObjectProcessViewSet, basename='product-object-processes')
router.register(r'product-object-process-logs', ProductObjectProcessLogViewSet, basename='product-object-process-logs')
router.register(r'(?P<group_id>\d+)/admin-process/places-in-groups', PlaceInGroupAdmin, basename='places-in-groups-admin')
router.register(r'(?P<product_id>\d+)/admin-objects', ProductObjectAdminViewSet)
router.register(r'admin-objects',ProductObjectAdminViewSet,basename='admin-objects')

router.register(r'bad-logs', LogFromMistakeData, basename='bad_logs')


urlpatterns = [
    path('product-object/move/<uuid:process_uuid>/', ProductMoveView.as_view(), name='product-move'),
    path('product-object/move-list/<uuid:process_uuid>/', ProductMoveListView.as_view(), name='product-move-list'),

    path('start-new-prod/<uuid:process_uuid>/', ProductStartNewProduction.as_view(), name='start-prouduction'),
    path('continue-prod/<uuid:process_uuid>/', ContinueProduction.as_view(), name='continue-prouduction'),
    path('retooling/<uuid:process_uuid>/', RetoolingView.as_view(), name='continue-prouduction'),
    path('start-new-prod-stencil/<uuid:process_uuid>/', StencilStartNewProd.as_view(), name='stencil-start-prod'),

    path('trash-obj/<uuid:process_uuid>/', ScrapProduct.as_view(), name='scrap-product'),
    
    path('<int:product_id>/<uuid:process_uuid>/bulk-create/', BulkProductObjectCreateView.as_view(), name='bulk-product-object-create'),
    path('<int:product_id>/<uuid:process_uuid>/bulk-create-to-mother/', BulkProductObjectCreateAndAddMotherView.as_view(), name='bulk-product-object-create-to-mother'),
    
    path('kill-app/', AppKillStatusView.as_view(), name='kill-app'),
    
    path('<int:product_id>/graph-import/', GraphImportView.as_view(), name='graph-import'),
    path('get-statuses-groups/', ListGroupsStatuses.as_view(), name='list-group-statuses'),
    path('counter-products/', SubProductsCounter.as_view(), name='couter-products'),

    # admin fetaures
    path('admin-process/process-list/', ProductProcessList.as_view(), name='process-list-admin'),

    path('process/<uuid:process_id>/admin-logs/', UnifiedLogsViewSet.as_view({'get': 'list'})),
    path('place/<int:place_id>/admin-logs/', UnifiedLogsViewSet.as_view({'get': 'list'})),
    path('product/<int:product_id>/admin-logs/', UnifiedLogsViewSet.as_view({'get': 'list'})),

    path('process/helper/<int:product_id>/', ProductObjectAdminViewSetProcessHelper.as_view(), name='helper-process'),
    path('place/helper/<int:product_id>/', ProductObjectAdminViewSetPlaceHelper.as_view(), name='helper-process'),
    path('admin/change-checking/<int:pk>/', GroupUpdateStatus.as_view(), name='change-checking')
]

urlpatterns += router.urls