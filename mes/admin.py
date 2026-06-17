from django.contrib import admin
from .models import *


admin.site.register(PasswordToUnlock)
admin.site.register(CheckMachine)
admin.site.register(UnlockHistory)