import django_filters
from .models import SpeaCard

class SpeaCardFilter(django_filters.FilterSet):
    is_main_wardrobe = django_filters.BooleanFilter(method='filter_is_main_wardrobe')
    location_in_company = django_filters.BooleanFilter(method='filter_location_in_company')

    class Meta:
        model = SpeaCard
        fields = ['category', 'is_broken', 'sn', 'location_in_company']

    def filter_is_main_wardrobe(self, queryset, name, value):
        if value is True:
            return queryset.filter(location__name='Szafa')
        elif value is False:
            return queryset.exclude(location__name='Szafa')
        
        return queryset
    
    def filter_location_in_company(self, queryset, name, value):
        if value is True:
            return queryset.filter(out_of_company=False).exclude(location__name='Szafa')
        if value is False:
            return queryset.filter(out_of_company=True)
        
        return queryset