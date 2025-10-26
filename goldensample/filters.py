import django_filters
from .models import MasterSample

class MasterSampleFilter(django_filters.FilterSet):
    client = django_filters.BaseInFilter(field_name="client", lookup_expr="in")
    process_name = django_filters.BaseInFilter(field_name="process_name", lookup_expr="in")
    master_type = django_filters.BaseInFilter(field_name="master_type", lookup_expr="in")
    departament = django_filters.BaseInFilter(field_name="departament", lookup_expr="in")

    class Meta:
        model = MasterSample
        fields = ['client', 'process_name', 'master_type', 'departament']
