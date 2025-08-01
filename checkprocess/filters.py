import django_filters
from .models import ProductObject, ProductObjectProcessLog


class ProductObjectFilter(django_filters.FilterSet):
    current_process = django_filters.UUIDFilter(field_name='current_process__id')
    current_place = django_filters.CharFilter(field_name='current_place__name', lookup_expr='icontains')
    place_isnull = django_filters.BooleanFilter(field_name='current_place', lookup_expr='isnull')

    class Meta:
        model = ProductObject
        fields = ['current_process', 'current_place', 'place_isnull']
        

class ProductObjectProcessLogFilter(django_filters.FilterSet):
    serial_number = django_filters.CharFilter(field_name='product_object__serial_number', lookup_expr='iexact')
    full_sn = django_filters.CharFilter(field_name='product_object__full_sn', lookup_expr='iexact')

    class Meta:
        model = ProductObjectProcessLog
        fields = ['serial_number', 'full_sn']