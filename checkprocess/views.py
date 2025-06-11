from rest_framework import viewsets
from django.shortcuts import get_object_or_404

from .models import Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog
from .serializers import ProductSerializer, ProductProcessSerializer, ProductObjectSerializer, ProductObjectProcessSerializer, ProductObjectProcessLogSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class ProductProcessViewSet(viewsets.ModelViewSet):
    serializer_class = ProductProcessSerializer

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductProcess.objects.filter(product_id=product_id)

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, pk=product_id)
        serializer.save(product=product)


class ProductObjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProductObjectSerializer

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductObject.objects.filter(product_id=product_id)

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, pk=product_id)

        product_object = serializer.save(product=product)

        processes = ProductProcess.objects.filter(product=product)

        for process in processes:
            ProductObjectProcess.objects.create(
                product_object=product_object,
                process=process,
                is_completed=False
            )


class ProductObjectProcessViewSet(viewsets.ModelViewSet):
    serializer_class = ProductObjectProcessSerializer

    def get_queryset(self):
        product_object_id = self.kwargs.get('product_object_id')
        return ProductObjectProcess.objects.filter(product_object_id=product_object_id)

    def perform_create(self, serializer):
        product_object_id = self.kwargs.get('product_object_id')
        product_object = get_object_or_404(ProductObject, pk=product_object_id)
        serializer.save(product_object=product_object)


class ProductObjectProcessLogViewSet(viewsets.ModelViewSet):
    serializer_class = ProductObjectProcessLogSerializer

    def get_queryset(self):
        product_object_process_id = self.kwargs.get('product_object_process_id')
        return ProductObjectProcessLog.objects.filter(product_object_process_id=product_object_process_id)

    def perform_create(self, serializer):
        product_object_process_id = self.kwargs.get('product_object_process_id')
        pop = get_object_or_404(ProductObjectProcess, pk=product_object_process_id)
        serializer.save(product_object_process=pop)
