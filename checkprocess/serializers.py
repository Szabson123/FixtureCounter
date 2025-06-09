from rest_framework import serializers

from .models import ProductProcess, Product



class ProductProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProcess
        fields = ['id', 'name', 'is_required', 'order']


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name']