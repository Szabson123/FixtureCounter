from rest_framework import serializers
from .models import Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place, Edge


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name']
        

class PlaceSerializer(serializers.ModelSerializer):
    process_name = serializers.StringRelatedField(source='assigned_place.name', read_only=True)
    class Meta:
        model = Place
        fields = ['id', 'name', 'process_name']


class ProductProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProcess
        fields = ['id', 'product', 'type', 'label', 'pos_x', 'pos_y', 'is_required']

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

    initial_place = serializers.SerializerMethodField()
    initial_who_entry = serializers.SerializerMethodField()

    current_process = serializers.StringRelatedField(read_only=True)
    current_place = serializers.StringRelatedField(read_only=True)
    mother_sn = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ProductObject
        fields = [
            'id', 'full_sn', 'serial_number', 'created_at',
            'production_date', 'expire_date',
            'place_name', 'who_entry', 'initial_who_entry',
            'current_process', 'current_place', 'initial_place', 'exp_date_in_process', 'quranteen_time', 'mother_sn', 'is_mother'
        ]
        read_only_fields = [
            'serial_number', 'production_date', 'expire_date',
            'current_process', 'current_place',
        ]

    def get_initial_place(self, obj):
        log = ProductObjectProcessLog.objects.filter(
            product_object_process__product_object=obj,
            product_object_process__process__order=1
        ).order_by('entry_time').first()
        return log.place.name if log and log.place else None

    def get_initial_who_entry(self, obj):
        log = ProductObjectProcessLog.objects.filter(
            product_object_process__product_object=obj,
            product_object_process__process__order=1
        ).order_by('entry_time').first()
        return log.who_entry if log else None


class ProductObjectProcessSerializer(serializers.ModelSerializer):
    process_name = serializers.StringRelatedField(source='process.name', read_only=True)
    
    class Meta:
        model = ProductObjectProcess
        fields = ['id', 'process_name']


class ProductObjectProcessLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductObjectProcessLog
        fields = ['id', 'entry_time', 'who_entry', 'exit_time', 'who_exit']



class ProductMoveSerializer(serializers.Serializer):
    full_sn = serializers.CharField()
    who_exit = serializers.CharField()


class ProductReceiveSerializer(serializers.Serializer):
    full_sn = serializers.CharField()
    who_entry = serializers.CharField()
    place_name = serializers.CharField()
    

class EdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edge
        fields = ['id', 'source', 'target', 'type', 'animated', 'label']

    def to_internal_value(self, data):
        return {
            'id': data.get('id'),
            'type': data.get('type', 'default'),
            'animated': data.get('animated', False),
            'label': data.get('label', ''),
            'source': data.get('source'),
            'target': data.get('target'),
        }