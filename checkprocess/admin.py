from django.contrib import admin
from .models import *


admin.site.register(Product)
admin.site.register(ProductObject)
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
