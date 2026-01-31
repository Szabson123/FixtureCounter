from rest_framework import serializers

from .models import SpeaCard, DiagnosisFile, LocationSpea
from django.db import transaction
from django.core.files.uploadedfile import UploadedFile


class LocationSpeaSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationSpea
        fields = ['id', 'name']
        extra_kwargs = {
            'name': {'validators': []}
        }


class DiagnosisFileSerializer(serializers.ModelSerializer):
    active = serializers.BooleanField(read_only=True)
    class Meta:
        model = DiagnosisFile
        fields = ['id', 'active', 'file']


class SpeaCardSerializer(serializers.ModelSerializer):
    location = LocationSpeaSerializer()
    is_broken = serializers.BooleanField(read_only=True)
    first_file = serializers.SerializerMethodField()

    class Meta:
        model = SpeaCard
        fields = ['id', 'sn', 'category', 'location', 'is_broken', 'first_file']

    def get_first_file(self, obj):
        file_path = getattr(obj, 'first_file', None)
        if not file_path:
            return None

        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f"/media/{file_path}")
        
        return f"/media/{file_path}"
        
    def create(self, validated_data):
        location_data = validated_data.pop('location', None)
        
        with transaction.atomic():
            location_instance = None
            if location_data:
                location_instance, _ = LocationSpea.objects.get_or_create(**location_data)

            spea_card = SpeaCard.objects.create(location=location_instance, **validated_data)
        
        return spea_card
    

class SpeaCardLocationSerializer(serializers.ModelSerializer):
        class Meta:
            model = LocationSpea
            fields = ['id', 'name']
            extra_kwargs = {
                'name': {'validators': []}
            }

