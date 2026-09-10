from django.contrib import admin
from .models import *

@admin.register(SnToBoard)
class SnToBoardAdmin(admin.ModelAdmin):
    list_display = (
        'sn',
        'pallet',
        'place_num',
        'aoi_result',
        'ict_result',
        'fvt_result',
        'full_result',
    )
    list_filter = ('full_result', 'pallet')
    search_fields = ('sn',)

@admin.register(PalletFullInfo)
class PalletFullInfoAdmin(admin.ModelAdmin):
    list_display = ('pallet_number', 'db_board_id', 'full_used', 'created_at')