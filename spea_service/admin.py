from django.contrib import admin
from .models import *


admin.site.register(Machine)
admin.site.register(FullValidationMachineModel)
admin.site.register(EndedCodesWithQueue)
admin.site.register(GoldenTypeValidate)
admin.site.register(TestedSn)
admin.site.register(ForceValidMachine)
admin.site.register(ValidPasswordLog)
admin.site.register(ValidPassword)

# Register your models here.
