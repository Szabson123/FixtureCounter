from django.urls import path, include
from .views import *


urlpatterns = [
    path('unluck-history/', UnlockHistoryView.as_view(), name='create-diag-file')
]
