from django.contrib import admin
from .models import *

admin.site.register(TimerGroup)
admin.site.register(CodeSmd)
admin.site.register(ClientName)
admin.site.register(ProcessName)
admin.site.register(TypeName)
admin.site.register(Department)
admin.site.register(EndCode)

admin.site.register(MachineGoldensTime)
admin.site.register(EndCodeTimeFWK)
admin.site.register(LastResultFWK)
admin.site.register(TempCheckMasterFWK)
admin.site.register(TempMasterShow)

@admin.register(MasterSample)
class MasterSampleAdmin(admin.ModelAdmin):
    search_fields = ('sn', )