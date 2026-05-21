from rest_framework import serializers
from django.utils import timezone

from .models import Machine
from .validators import validate_unique_values
from goldensample.models import MasterSample


# First serializer to prepare mass production
class GoldensMainValidationSerializer(serializers.Serializer):
    goldens = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
        validators=[validate_unique_values]
    )
    machine_name = serializers.CharField(allow_empty=False, required=True)
    phase_id = serializers.CharField(allow_empty=False, required=True)

    def validate_goldens(self, values):
        # N+1 Problem but we don't need optim here couse max goldens is 10
        for golden in values:
            try:
                MasterSample.objects.get(sn=golden, expire_date__gte=timezone.now())
            except MasterSample.DoesNotExist:
                raise serializers.ValidationError({"error": f"{golden} - does not exist or is expired"})
            
        return values
    