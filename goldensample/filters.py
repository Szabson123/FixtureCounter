import django_filters
from .models import MasterSample

class MasterSampleFilter(django_filters.FilterSet):
    client = django_filters.BaseInFilter(field_name="client", lookup_expr="in")
    process_name = django_filters.BaseInFilter(field_name="process_name", lookup_expr="in")
    master_type = django_filters.BaseInFilter(field_name="master_type", lookup_expr="in")
    departament = django_filters.BaseInFilter(field_name="departament", lookup_expr="in")
    additional_project_name = django_filters.BaseInFilter(field_name="additional_project_name", lookup_expr="in")
    
    endcodes = django_filters.BaseInFilter(field_name="endcodes__code", lookup_expr="in", distinct=True)
    code_smd = django_filters.BaseInFilter(field_name="code_smd__code", lookup_expr="in", distinct=True)

    class Meta:
        model = MasterSample
        fields = ['client', 'process_name', 'master_type', 'departament', 'additional_project_name', 'endcodes', 'code_smd']
