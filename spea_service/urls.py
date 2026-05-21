from django.urls import path
from .views import *


urlpatterns = [
    path('golden-prepare-check/', GoldensPrepareCheck.as_view(), name='unlig-statues'),
]
