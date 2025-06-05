from django.contrib import admin
from .models import *


admin.site.register(GroupVariantCode)
admin.site.register(VariantCode)
admin.site.register(GoldenSample)
admin.site.register(CounterOnGolden)
admin.site.register(MapSample)