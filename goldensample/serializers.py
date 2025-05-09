from rest_framework import serializers
from .models import ProductFamily, VariantCode, GoldenSampleCode


class GoldenSampleCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoldenSampleCode
        fields = ['id', 'sample_code']


class VariantCodeSerializer(serializers.ModelSerializer):
    golden_samples = GoldenSampleCodeSerializer(source='goldensamplecode_set', many=True, read_only=True)

    class Meta:
        model = VariantCode
        fields = ['id', 'code', 'golden_samples']


class ProductFamilySerializer(serializers.ModelSerializer):
    variants = VariantCodeSerializer(source='variantcode_set', many=True, read_only=True)

    class Meta:
        model = ProductFamily
        fields = ['id', 'name', 'variants']
        
    
class ProductFamilyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductFamily
        fields = ['id', 'name']


class VariantCodeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantCode
        fields = ['id', 'code', 'product_family']


class GoldenSampleCodeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoldenSampleCode
        fields = ['id', 'sample_code', 'variant_code']