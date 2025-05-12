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
    

class GroupVariantCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupVariantCode
        fields = ['name']

class VariantCodeSerializer(serializers.ModelSerializer):
    group = GroupVariantCodeSerializer()

    class Meta:
        model = VariantCode
        fields = ['code', 'group']

class GetFullInfoSerializer(serializers.ModelSerializer):
    variant = VariantCodeSerializer()

    class Meta:
        model = GoldenSample
        fields = ['id', 'golden_code', 'type_golden', 'expire_date', 'variant']
