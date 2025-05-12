from django.urls import path
from .views import GoldenSampleCreateView, GoldenSampleCheckView, GroupFullListView, GoldenSampleTypeCheckView


urlpatterns = [
    path('add-golden/', GoldenSampleCreateView.as_view(), name='create_golden_sample'),
    path('check/', GoldenSampleCheckView.as_view(), name='check_golden_sample'),
    path('goldens-list/', GroupFullListView.as_view(), name='golden_sample_list'),
    path('type/', GoldenSampleTypeCheckView.as_view(), name='golden_sample_type_check'),

]