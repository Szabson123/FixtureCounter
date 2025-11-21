from rest_framework import serializers
from .models import (Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place, Edge,
                     ProductProcessDefault, ProductProcessFields, ProductProcessStart, ProductProcessCondition, ProductProcessEnding, ConditionLog, PlaceGroupToAppKill)

from datetime import timedelta
from django.utils import timezone
from rest_framework.exceptions import ValidationError

class ProductProcessDefaultsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProcessDefault
        exclude = ['product_process']


class ProductProcessStartsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProcessStart
        exclude = ['product_process']


class ProductProcessConditionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProcessCondition
        exclude = ['product_process']


class ProductProcessEndingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProcessEnding
        exclude = ['product_process']
        

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name']
        

class PlaceSerializer(serializers.ModelSerializer):
    process_name = serializers.StringRelatedField(source='assigned_place.name', read_only=True)
    class Meta:
        model = Place
        fields = ['id', 'name', 'process_name']


class ProductProcessFieldsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProcessFields
        fields = '__all__'
        

class ProductProcessSerializer(serializers.ModelSerializer):
    defaults = ProductProcessDefaultsSerializer(read_only=True)
    conditions = ProductProcessConditionsSerializer(read_only=True)
    starts = ProductProcessStartsSerializer(read_only=True)
    endings = ProductProcessEndingsSerializer(read_only=True)
    fields = ProductProcessFieldsSerializer(read_only=True)

    class Meta:
        model = ProductProcess
        fields = ['id', 'product', 'type', 'label', 'pos_x', 'pos_y', 'is_required',
                  'defaults', 'conditions', 'starts', 'endings', 'fields',]

    def to_internal_value(self, data):
        return {
            'id': data.get('id'),
            'type': data.get('type'),
            'pos_x': data.get('position', {}).get('x'),
            'pos_y': data.get('position', {}).get('y'),
            'label': data.get('data', {}).get('label'),
            'product': self.context.get('product'),
        }


class ProductObjectSerializer(serializers.ModelSerializer):
    place_name = serializers.CharField(write_only=True)
    who_entry = serializers.CharField(write_only=True)
    full_sn = serializers.CharField()
    mother_sn = serializers.CharField(write_only=True, required=False, allow_blank=True)
    sub_product_name = serializers.SerializerMethodField()
    current_place_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductObject
        fields = [
                'id', 'full_sn', 'serial_number', 'created_at',
                'production_date', 'expire_date',
                'place_name', 'who_entry', 'current_place_name', 'mother_object',
                'exp_date_in_process', 'quranteen_time', 'mother_sn', 'is_mother', 'sub_product', 'sub_product_name',
                'sito_cycles_count', 'sito_cycle_limit', 'max_in_process', 'last_move'
            ]
        read_only_fields = [
            'serial_number', 'production_date', 'expire_date',
            'current_process', 'current_place', 'sub_product_name'
        ]
        
    def get_current_place_name(self, obj):
        return obj.current_place.name if obj.current_place else None
        
    def get_sub_product_name(self, obj):
        if obj.sub_product:
            return obj.sub_product.name
        return 'No type'


class ProductObjectProcessSerializer(serializers.ModelSerializer):
    process_name = serializers.StringRelatedField(source='process.name', read_only=True)
    
    class Meta:
        model = ProductObjectProcess
        fields = ['id', 'process_name']


class ProductObjectProcessLogSerializer(serializers.ModelSerializer):
    full_sn = serializers.CharField(source='product_object.full_sn', read_only=True)
    process_name = serializers.CharField(source='process.label', read_only=True)
    place_name = serializers.CharField(source='place.name', read_only=True)

    class Meta:
        model = ProductObjectProcessLog
        fields = ['id', 'entry_time', 'who_entry', 'exit_time', 'who_exit', 'full_sn', 'process_name', 'place_name', 'movement_type']


class EdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edge
        fields = ['id', 'source', 'target', 'type', 'animated', 'label', 'source_handle', 'target_handle']

    def to_internal_value(self, data):
        return {
            'id': data.get('id'),
            'type': data.get('type', 'default'),
            'animated': data.get('animated', False),
            'label': data.get('label', ''),
            'source': data.get('source'),
            'target': data.get('target'),
            'source_handle': data.get('sourceHandle'),
            'target_handle': data.get('targetHandle'),
        }
        
class BulkProductObjectCreateSerializer(serializers.Serializer):
    place_name = serializers.CharField()
    who_entry = serializers.CharField()
    objects = serializers.ListField(child=serializers.DictField(child=serializers.CharField()))
    

class ConditionLogSerializer(serializers.ModelSerializer):
    result = serializers.BooleanField(allow_null=True, required=False)
    class Meta:
        model = ConditionLog
        fields = "__all__"


class BulkProductObjectCreateToMotherSerializer(serializers.Serializer):
    who_entry = serializers.CharField()
    objects = serializers.ListField(child=serializers.DictField(child=serializers.CharField()))
    mother_sn = serializers.CharField()


class PlaceGroupToAppKillSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = PlaceGroupToAppKill
        fields = ['id', 'name', 'last_check', 'status']

    def get_status(self, obj):
        if obj.last_check is None:
            return False
        return (timezone.now() - obj.last_check) <= timedelta(minutes=1)


class RetoolingSerializer(serializers.Serializer):
    place_name = serializers.CharField(required=True)
    who = serializers.CharField(required=True)
    movement_type = serializers.CharField(required=True)
    production_card = serializers.CharField(required=True)


class StencilStartProdSerializer(serializers.Serializer):
    place_name = serializers.CharField(required=True)
    movement_type = serializers.CharField(required=True)
    who = serializers.CharField(required=True)
    full_sn = serializers.CharField(required=True)

    def validate_movement_type(self, value):
        if value != 'receive':
            raise ValidationError("Tylko przyjmowanie dla tego enpointu")
        return value