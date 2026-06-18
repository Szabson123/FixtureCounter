from rest_framework import serializers
from .models import UnlockHistory

class UnlockHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = UnlockHistory
        fields = ['id', 'phase_id', 'internal_code', 'who', 'date_time']