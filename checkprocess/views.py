from django.shortcuts import render
from rest_framework import viewsets
from django.shortcuts import get_object_or_404

from .models import Product, ProductProcess
from .serializers import ProductSerializer, ProductProcessSerializer


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    

class ProcessProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductProcessSerializer

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductProcess.objects.filter(product_id=product_id)

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, pk=product_id)
        serializer.save(product=product)