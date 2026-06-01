from django.urls import path
from .views import *


urlpatterns = [
    path('golden-prepare-check/', GoldensPrepareCheck.as_view(), name='unlig-statues'),
    path('golden-types-check/', GoldenTypeCheck.as_view(), name='types-check'),
    path('production-observer/', ProductionObserverService.as_view(), name='observer'),

    path('force-validate-machine/', ForceValidateMachine.as_view(), name='force-validate'),
    path('invalidate-machine/', InValidateMachine.as_view(), name='invalidate'),
]
