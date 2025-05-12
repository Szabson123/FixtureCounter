from .models import *
from rest_framework import serializers


class GoldenSampleCreateSerializer(serializers.Serializer):
    sn = serializers.CharField()
    type_golden = serializers.ChoiceField(choices=GoldenTypes)
    variant_code = serializers.CharField()
    expire_date = serializers.DateField(required=False)
    

class GoldenSampleCheckSerializer(serializers.Serializer):
    goldens = serializers.ListField(
        child=serializers.CharField(), allow_empty=False
    )
    

class GroupMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupVariantCode
        fields = ['id', 'name']

class GoldenSampleSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoldenSample
        fields = ['id', 'golden_code', 'type_golden', 'expire_date']


class VariantFullSerializer(serializers.ModelSerializer):
    group = GroupMiniSerializer(read_only=True)
    goldens = GoldenSampleSimpleSerializer(source='goldensample_set', many=True)

    class Meta:
        model = VariantCode
        fields = ['code', 'group', 'goldens']