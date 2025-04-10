from django.urls import path
from .views import sse_updates

urlpatterns = [
    path('sse-updates/', sse_updates, name='sse-updates'),
]