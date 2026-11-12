from rest_framework import serializers
from django.utils import timezone

from datetime import timedelta

from .models import Machine, ForceValidMachine, FullValidationMachineModel, ValidPassword, EndedCodesWithQueue
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


class PasswordProtectedSerializer(serializers.Serializer):
    """Sprawdza haslo z tabeli ValidPassword i podaje instancje dalej do logowania."""
    password = serializers.CharField(allow_null=False, required=True, write_only=True)

    def validate(self, attrs):
        password = attrs.get('password')

        try:
            valid_password_instance = ValidPassword.objects.get(password=password)
        except ValidPassword.DoesNotExist:
            raise serializers.ValidationError({"password": "Podano niepoprawne hasło."})
        except ValidPassword.MultipleObjectsReturned:
            valid_password_instance = ValidPassword.objects.filter(password=password).first()

        attrs['valid_password_instance'] = valid_password_instance
        return attrs


class ForceValidMachineSerializerApp(PasswordProtectedSerializer):
    machine_name = serializers.CharField(allow_null=False, required=True)
    # Domyslnie 8h jak dotad (aplikacja na maszynie nie wysyla hours)
    hours = serializers.IntegerField(required=False, default=8, min_value=1)


class MachineInvalidateApp(PasswordProtectedSerializer):
    machine_name = serializers.CharField(allow_null=False, required=True)


class MachineInvalidate(serializers.Serializer):
    machine_name = serializers.CharField(allow_null=False, required=True)


class MachineInvalidation(serializers.ModelSerializer):
    class Meta:
        model = ForceValidMachine
        fields = ['id', 'date_time_start', 'date_time_end', 'is_valid']


class MachineFullValidation(serializers.ModelSerializer):
    class Meta:
        model = FullValidationMachineModel
        fields = ['id', 'is_valid', 'time_date', 'ended']


# Tyle samo godzin liczy SpeaService (check-sns) od time_date ostatniej walidacji
FULL_VALIDATION_HOURS = 8


class EndedCodesWithQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = EndedCodesWithQueue
        fields = ['queue', 'code']


class LastFullValidationSerializer(serializers.ModelSerializer):
    codes = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()

    class Meta:
        model = FullValidationMachineModel
        fields = ['id', 'is_valid', 'ended', 'time_date', 'expires_at', 'codes']

    def get_codes(self, obj):
        queues = sorted(obj.queues.all(), key=lambda q: q.queue)
        return EndedCodesWithQueueSerializer(queues, many=True).data

    def get_expires_at(self, obj):
        if not obj.time_date:
            return None
        return serializers.DateTimeField().to_representation(
            obj.time_date + timedelta(hours=FULL_VALIDATION_HOURS)
        )


class MachineMainSerializer(serializers.ModelSerializer):
    forcevalidation = MachineInvalidation(many=True, read_only=True)
    fullvalidation = MachineFullValidation(many=True, read_only=True)
    last_full_validation = serializers.SerializerMethodField()

    class Meta:
        model = Machine
        fields = ['id', 'name', 'forcevalidation', 'fullvalidation', 'last_full_validation']

    def get_last_full_validation(self, obj):
        last = self.context.get('last_full_validations', {}).get(obj.id)
        return LastFullValidationSerializer(last).data if last else None