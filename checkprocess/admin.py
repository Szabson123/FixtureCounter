from django.contrib import admin
from .models import *


admin.site.register(Product)
admin.site.register(ProductObject)
admin.site.register(ProductProcess)
admin.site.register(ProductObjectProcess)
admin.site.register(ProductObjectProcessLog)
admin.site.register(Place)
admin.site.register(AppToKill)

