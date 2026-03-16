from django.contrib import admin
from .models import *


admin.site.register(UserUnlinkerProfile)
admin.site.register(ProcessUnlinking)
admin.site.register(ProcessUnlinkingData)

