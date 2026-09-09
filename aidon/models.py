from django.db import models
from django.db import models
from django.db.models import Q


class PalletFullInfo(models.Model):
    db_board_id = models.IntegerField()
    pallet_number = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    full_used = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['db_board_id', 'pallet_number'],
                name='unique_board_pallet'
            )
        ]
        indexes = [
            models.Index(
                fields=['pallet_number'],
                name='idx_active_pallet_num',
                condition=Q(full_used=False)
            ),
        ]


class SnToBoard(models.Model):
    pallet = models.ForeignKey(PalletFullInfo, on_delete=models.CASCADE, related_name='sn_boards')
    sn = models.CharField(max_length=255, db_index=True)
    place_num = models.IntegerField()
    aoi_result = models.BooleanField(null=True, blank=True)
    ict_result = models.BooleanField(null=True, blank=True)
    fvt_result = models.BooleanField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['pallet', 'place_num'], name='idx_sn_pallet_place'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['pallet', 'place_num'],
                name='unique_pallet_place'
            )
        ]

# Palletka numer
# SN NUMER 1, 2, 3...
# DATA 
# DB BOARD ID -> WAŻNE UNIKALNE SAMO I UNIKALNE Z PALLET NUMBER
# POZYCJA -> 0 TO PALETKA
# RESULT W OSTATNIM PROCESIE (NA TERAZ USTALAM ŻE MOGA BYC TYLKO 2 FVT i ICT, AOI