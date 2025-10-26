from django.contrib import admin
from .models import *


admin.site.register(GroupVariantCode)
admin.site.register(VariantCode)
admin.site.register(GoldenSample)
admin.site.register(CounterOnGolden)
admin.site.register(MapSample)
admin.site.register(PcbEvent)


admin.site.register(TimerGroup)
admin.site.register(CodeSmd)
admin.site.register(ClientName)
admin.site.register(ProcessName)
admin.site.register(TypeName)
admin.site.register(Department)
admin.site.register(MasterSample)
admin.site.register(EndCode)