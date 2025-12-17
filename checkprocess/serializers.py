from rest_framework import serializers
from .models import (Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place, Edge, LogFromMistake, AppToKill,
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
        fields = ['id', 'product', 'type', 'label', 'pos_x', 'pos_y', 'is_required', 'search',
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
                'sito_cycles_count', 'sito_cycle_limit', 'max_in_process', 'last_move', 'sito_basic_unnamed_place', 'free_plain_text'
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
        fields = ['id', 'entry_time', 'who_entry', 'full_sn', 'process_name', 'place_name', 'movement_type']


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
    

class LogFromMistakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogFromMistake
        fields = '__all__'


class ProductProcessSimpleSerializer(serializers.ModelSerializer):
    product_name = serializers.StringRelatedField(source='product.name', read_only=True)
    class Meta:
        model = ProductProcess
        fields = ['id', 'product_name', 'label']


class AppToKillSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppToKill
        fields = ['killing_flag']


class PlaceSerializerAdmin(serializers.ModelSerializer):
    apptokill = AppToKillSerializer()

    class Meta:
        model = Place
        fields = ['id', 'name', 'apptokill']

    def update(self, instance, validated_data):
        apptokill_data = validated_data.pop("apptokill", None)

        instance = super().update(instance, validated_data)

        if apptokill_data is not None:
            apptokill_instance = getattr(instance, 'apptokill', None)

            if apptokill_instance:
                serializer = AppToKillSerializer(
                    instance=apptokill_instance,
                    data=apptokill_data,
                    partial=True
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()

        return instance
    

class UnifyLogsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    log_type = serializers.CharField()
    date = serializers.DateTimeField()

    who_value = serializers.CharField(allow_null=True)
    movement = serializers.CharField(allow_null=True)
    info = serializers.CharField(allow_null=True)

    proc_id = serializers.UUIDField(allow_null=True)
    proc_label = serializers.CharField(allow_null=True)
    pl_id = serializers.IntegerField(allow_null=True)
    pl_name = serializers.CharField(allow_null=True)


class ProductObjectAdminSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    sub_product_name = serializers.CharField(source='sub_product.name', read_only=True)
    current_place_name = serializers.CharField(source='current_place.name', read_only=True)
    current_process_name = serializers.CharField(source='current_process.label', read_only=True)

    current_place_id = serializers.PrimaryKeyRelatedField(
        queryset=Place.objects.all(),
        source='current_place',
        write_only=True,
        required=False,
        allow_null=True,
    )

    current_process_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductProcess.objects.all(),
        source='current_process',
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ProductObject
        fields = ['id', 'is_mother',
                  'last_move', 'current_process_id', 'current_place_id', 'sito_basic_unnamed_place',
                  'free_plain_text', 'serial_number', 'full_sn', 'created_at', 'expire_date',
                  'production_date', 'exp_date_in_process', 'quranteen_time', 'max_in_process',
                  'ex_mother', 'sito_cycle_limit', 'sito_cycles_count', 'end', 'is_full',
                  'current_process_name', 'current_place_name', 'product_name', 'sub_product_name']


class ProductObjectAdminSerializerProcessHelper(serializers.ModelSerializer):
    class Meta:
        model = ProductProcess
        fields = ['id', 'label']

    
class ProductObjectAdminSerializerPlaceHelper(serializers.ModelSerializer):
    class Meta:
        model = ProductProcess
        fields = ['id', 'name']