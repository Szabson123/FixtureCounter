from django.contrib import admin
from .models import *

admin.site.register(Fixture)
admin.site.register(Counter)
admin.site.register(CounterSumFromLastMaint)
admin.site.register(FullCounter)
admin.site.register(CounterHistory)
# Register your models here.
