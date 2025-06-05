from .models import *
from rest_framework import serializers


class GoldenCounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CounterOnGolden
        fields = ['id', 'golden_sample', 'counter']


class GoldenSampleCreateSerializer(serializers.Serializer):
    sn = serializers.CharField()
    type_golden = serializers.ChoiceField(choices=GoldenTypes)
    variant_code = serializers.CharField()
    variant_name = serializers.CharField(required=False, allow_blank=True)
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
    counter = serializers.SerializerMethodField()

    class Meta:
        model = GoldenSample
        fields = ['id', 'golden_code', 'type_golden', 'expire_date', 'counter']

    def get_counter(self, obj):
        try:
            return obj.counterongolden.counter
        except:
            return None


class VariantFullSerializer(serializers.ModelSerializer):
    group = GroupMiniSerializer(read_only=True)
    goldens = GoldenSampleSimpleSerializer(source='goldensample_set', many=True)
    counter = serializers.IntegerField(read_only=True)

    class Meta:
        model = VariantCode
        fields = ['code', 'name', 'group', 'goldens', 'counter']


class VariantShortSerializer(serializers.ModelSerializer):
    golden_count = serializers.SerializerMethodField()

    class Meta:
        model = VariantCode
        fields = ['id', 'code', 'name', 'group', 'golden_count']

    def get_golden_count(self, obj):
        return obj.goldensample_set.count()
        
        
class GoldenSampleDetailedSerializer(serializers.ModelSerializer):
    counter = serializers.SerializerMethodField()
    variant = VariantShortSerializer()

    class Meta:
        model = GoldenSample
        fields = ['id', 'golden_code', 'expire_date', 'type_golden', 'counter', 'variant']

    def get_counter(self, obj):
        try:
            return obj.counterongolden.counter
        except:
            return None
        

class MapSampleSerailizer(serializers.ModelSerializer):
    class Meta:
        fields = ['id', 'input', 'output']