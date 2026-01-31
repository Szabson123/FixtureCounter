import django_filters
from .models import SpeaCard

class SpeaCardFilter(django_filters.FilterSet):
    is_main_wardrobe = django_filters.BooleanFilter(method='filter_is_main_wardrobe')

    class Meta:
        model = SpeaCard
        fields = ['category', 'is_broken', 'sn']

    def filter_is_main_wardrobe(self, queryset, name, value):
        """
        value: True lub False (przekazane w URL)
        """
        if value is True:
            return queryset.filter(location__name='Szafa')
        elif value is False:
            return queryset.exclude(location__name='Szafa')
        
        return queryset