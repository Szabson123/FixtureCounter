from rest_framework import viewsets
from django.shortcuts import get_object_or_404, get_object_or_404

from .models import Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place
from .serializers import ProductSerializer, ProductProcessSerializer, ProductObjectSerializer, ProductObjectProcessSerializer, ProductObjectProcessLogSerializer
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from .filters import ProductObjectFilter

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
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductObjectFilter

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductObject.objects.filter(product_id=product_id)

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, pk=product_id)

        place_name = self.request.data.get('place')
        who_entry = self.request.data.get('who_entry')

        if not place_name or not who_entry:
            raise ValidationError("Brakuje 'place' lub 'who_entry' w danych.")

        place_obj, _ = Place.objects.get_or_create(name=place_name)

        product_object = serializer.save(product=product)

        processes = ProductProcess.objects.filter(product=product)

        for process in processes:
            po_process = ProductObjectProcess.objects.create(
                product_object=product_object,
                process=process,
                is_completed=False
            )

            if process.order == 1:
                ProductObjectProcessLog.objects.create(
                    product_object_process=po_process,
                    who_entry=who_entry,
                    place=place_obj
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
