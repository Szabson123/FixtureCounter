import django_filters
from .models import ProductObject


class ProductObjectFilter(django_filters.FilterSet):
    process_id = django_filters.NumberFilter(
        field_name='assigned_processes__process_id'
    )
    place_id = django_filters.NumberFilter(
        field_name='assigned_processes__logs__place_id'
    )

    class Meta:
        model = ProductObject
        fields = ['process_id', 'place_id']
