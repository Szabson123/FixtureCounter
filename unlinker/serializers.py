from rest_framework import serializers
from .models import ProcessUnlinkingData, ProcessUnlinking, UserUnlinkerProfile


class UserUnlinkerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserUnlinkerProfile
        fields = ['id', 'user_card']


class ProcessUnlinkingDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessUnlinkingData
        fields = ['id', 'code', 'phases', 'error_code']


class ProcessUnlinkingSerializer(serializers.ModelSerializer):
    processdata = ProcessUnlinkingDataSerializer(many=True, read_only=True)
    class Meta:
        model = ProcessUnlinking
        fields = ['id', 'status', 'processdata', 'time_date']

    
class NoneSerializer(serializers.Serializer):
    pass


class UnlinkingRequestSerializer(serializers.Serializer):
    product = serializers.CharField(max_length=255)
    top_level_process = serializers.CharField(max_length=255)
    full_sn_list = serializers.DictField(child=serializers.BooleanField())
    processes = serializers.ListField(child=serializers.CharField())
    sn_list_to_rework = serializers.ListField(child=serializers.CharField())