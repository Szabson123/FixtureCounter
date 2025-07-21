import django_filters
from .models import ProductObject


class ProductObjectFilter(django_filters.FilterSet):
    current_process = django_filters.UUIDFilter(field_name='current_process__id')
    current_place = django_filters.CharFilter(field_name='current_place__name', lookup_expr='icontains')
    place_isnull = django_filters.BooleanFilter(field_name='current_place', lookup_expr='isnull')

    class Meta:
        model = ProductObject
        fields = ['current_process', 'current_place', 'place_isnull']