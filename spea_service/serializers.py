from rest_framework import serializers
from django.utils import timezone

from .models import Machine, ForceValidMachine
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
        valid_sns = set(
            MasterSample.objects.filter(
                sn__in=values, 
                expire_date__gte=timezone.now()
            ).values_list('sn', flat=True)
        )
        
        response_data = {}
        has_errors = False

        for golden in values:
            if golden in valid_sns:
                response_data[golden] = ""
            else:
                response_data[golden] = "does not exist or is expired" 
                has_errors = True

        if has_errors:
            raise serializers.ValidationError(response_data)
            
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


class MachineInvalidation(serializers.ModelSerializer):
    class Meta:
        model = ForceValidMachine
        fields = ['id', 'date_time_start', 'date_time_end', 'is_valid']


class MachineMainSerializer(serializers.ModelSerializer):
    forcevalidation = MachineInvalidation(many=True, read_only=True)
    class Meta:
        model = Machine
        fields = ['id', 'name', 'forcevalidation']