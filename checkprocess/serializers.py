from rest_framework import serializers
from .models import Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name']


class ProductProcessSerializer(serializers.ModelSerializer):
    product_name = serializers.StringRelatedField(source='product.name', read_only=True)
    class Meta:
        model = ProductProcess
        fields = ['id', 'product_name', 'name', 'is_required', 'order']


class ProductObjectSerializer(serializers.ModelSerializer):
    initial_place = serializers.SerializerMethodField()
    who_entry = serializers.SerializerMethodField()

    class Meta:
        model = ProductObject
        fields = ['id', 'serial_number', 'created_at', 'initial_place', 'who_entry']

    def get_initial_place(self, obj):
        log = ProductObjectProcessLog.objects.filter(
            product_object_process__product_object=obj,
            product_object_process__process__order=1
        ).order_by('entry_time').first()

        return log.place.name if log and log.place else None

    def get_who_entry(self, obj):
        log = ProductObjectProcessLog.objects.filter(
            product_object_process__product_object=obj,
            product_object_process__process__order=1
        ).order_by('entry_time').first()

        return log.who_entry if log else None


class ProductObjectProcessSerializer(serializers.ModelSerializer):
    process_name = serializers.StringRelatedField(source='process.name', read_only=True)
    
    class Meta:
        model = ProductObjectProcess
        fields = ['id', 'process_name', 'is_completed', 'completed_at']


class ProductObjectProcessLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductObjectProcessLog
        fields = ['id', 'entry_time', 'who_entry', 'exit_time', 'who_exit']
