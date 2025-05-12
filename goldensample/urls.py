from django.urls import path
from .views import GoldenSampleCreateView, GoldenSampleCheckView, GoldenSampleListView


urlpatterns = [
    path('add-golden/', GoldenSampleCreateView.as_view(), name='create_golden_sample'),
    path('check/', GoldenSampleCheckView.as_view(), name='check_golden_sample'),
    path('goldens-list/', GoldenSampleListView.as_view(), name='golden_sample_list'),

]