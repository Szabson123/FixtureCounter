from django.contrib import admin
from .models import *
from django import forms

admin.site.register(Fixture)
admin.site.register(Counter)
admin.site.register(CounterSumFromLastMaint)
admin.site.register(FullCounter)
# Register your models here.


class CounterHistoryForm(forms.ModelForm):
    class Meta:
        model = CounterHistory
        fields = '__all__'

@admin.register(CounterHistory)
class CounterHistoryAdmin(admin.ModelAdmin):
    form = CounterHistoryForm
    list_display = ('fixture', 'counter', 'date')
    fields = ('fixture', 'counter', 'date')

    def get_form(self, request, obj=None, **kwargs):
        self.model._meta.get_field('date').editable = True
        return super().get_form(request, obj, **kwargs)