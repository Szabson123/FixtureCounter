from django.urls import path
from .views import *


urlpatterns = [
    path('golden-prepare-check/', GoldensPrepareCheck.as_view(), name='unlig-statues'),
    path('golden-types-check/', GoldenTypeCheck.as_view(), name='types-check'),
    path('golden-observer/', ProductionObserverService.as_view(), name='observer')
]
