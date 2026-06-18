from rest_framework import serializers
from django.utils import timezone

from .models import Machine
from .validators import validate_unique_values
from goldensample.models import MasterSample


# First serializer to prepare mass production
class GoldensMainValidationSerializer(serializers.Serializer):
    goldens = serializers.ListField(
        child=serializers.CharField(),
        allow_null=False,
        validators=[validate_unique_values]
    )
    machine_name = serializers.CharField(allow_null=False, required=True)
    phase_id = serializers.CharField(allow_null=False, required=True)
    unique_id = serializers.UUIDField(allow_null=True, required=False)

    def validate_goldens(self, values):
        # N+1 Problem but we don't need optim here couse max goldens is 10
        response_data = {}
        for golden in values:
            try:
                MasterSample.objects.get(sn=golden, expire_date__gte=timezone.now())
                response_data[golden] = ""
            except MasterSample.DoesNotExist:
                response_data[golden] = "does not exist or is expired"

        if response_data:
            raise serializers.ValidationError({"error": response_data})
            
        return values
    

class GoldensTypeValidationSerializer(serializers.Serializer):
    goldens = serializers.DictField(
        child=serializers.CharField(),
        allow_empty=False,
        allow_null=False,
    )
    machine_name = serializers.CharField(allow_null=False, required=True)


class ProductionObserverSerializer(serializers.Serializer):
    sns = serializers.ListField(
        child=serializers.CharField(),
        allow_null=False,
        validators=[validate_unique_values]
    )
    machine_name = serializers.CharField(allow_null=False, required=True)
    phase_id = serializers.CharField(allow_null=False, required=True)


class ForceValidMachineSerializer(serializers.Serializer):
    machine_name = serializers.CharField(allow_null=False, required=True)
    hours = serializers.IntegerField(allow_null=False, required=True)


class MachineInvalidate(serializers.Serializer):
    machine_name = serializers.CharField(allow_null=False, required=True)