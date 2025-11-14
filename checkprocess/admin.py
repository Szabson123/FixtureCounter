from django.contrib import admin
from .models import *


admin.site.register(Product)

@admin.register(ProductObject)
class ProductObjectAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'full_sn', 'product', 'current_process', 'current_place', 'created_at')
    search_fields = ('serial_number', 'full_sn')
    
admin.site.register(ProductProcess)
admin.site.register(ProductObjectProcess)
admin.site.register(ProductObjectProcessLog)
admin.site.register(Place)
admin.site.register(AppToKill)
admin.site.register(SubProduct)
admin.site.register(Edge)
admin.site.register(ProductProcessDefault)
admin.site.register(ProductProcessCondition)
admin.site.register(ProductProcessStart)
admin.site.register(ProductProcessEnding)
admin.site.register(OneToOneMap)
admin.site.register(LastProductOnPlace)
admin.site.register(ConditionLog)
admin.site.register(PlaceGroupToAppKill)
admin.site.register(EdgeOptionsSets)
admin.site.register(DataBasesSpiMap)
