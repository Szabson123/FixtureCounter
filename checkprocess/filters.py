import django_filters
from .models import ProductObject


class ProductObjectFilter(django_filters.FilterSet):
    current_process = django_filters.NumberFilter(field_name='current_process__id')
    current_place = django_filters.CharFilter(field_name='current_place__name', lookup_expr='icontains')

    class Meta:
        model = ProductObject
        fields = ['current_process', 'current_place']