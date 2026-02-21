from django.urls import path, include
from .views import *
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'objects', SpeaCardViewSet, basename='spea-card')

urlpatterns = [
    path('', include(router.urls)),
    path('create-diag-file/<int:spea_card_id>/', CreateFileToBrokenCard.as_view(), name='create-diag-file')
]
