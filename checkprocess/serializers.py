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
    class Meta:
        model = ProductObject
        fields = ['id', 'serial_number', 'created_at']


class ProductObjectProcessSerializer(serializers.ModelSerializer):
    process_name = serializers.StringRelatedField(source='process.name', read_only=True)
    
    class Meta:
        model = ProductObjectProcess
        fields = ['id', 'process_name', 'is_completed', 'completed_at']


class ProductObjectProcessLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductObjectProcessLog
        fields = ['id', 'entry_time', 'who_entry', 'exit_time', 'who_exit']
