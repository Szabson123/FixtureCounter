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
        fields = ['id', 'status', 'processdata']