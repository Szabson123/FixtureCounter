from rest_framework import viewsets, status
from .models import ProductFamily, VariantCode, GoldenSampleCode
from .serializers import (
    ProductFamilySerializer, ProductFamilyCreateSerializer,
    VariantCodeSerializer, VariantCodeCreateSerializer,
    GoldenSampleCodeSerializer, GoldenSampleCodeCreateSerializer
)

from rest_framework.views import APIView
from rest_framework.response import Response


class ProductFamilyViewSet(viewsets.ModelViewSet):
    queryset = ProductFamily.objects.all()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductFamilyCreateSerializer
        return ProductFamilySerializer


class VariantCodeViewSet(viewsets.ModelViewSet):
    queryset = VariantCode.objects.select_related('product_family').all()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return VariantCodeCreateSerializer
        return VariantCodeSerializer


class GoldenSampleCodeViewSet(viewsets.ModelViewSet):
    queryset = GoldenSampleCode.objects.select_related('variant_code').all()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return GoldenSampleCodeCreateSerializer
        return GoldenSampleCodeSerializer
    

class VerifyGoldenSamplesView(APIView):
    def post(self, request):
        family_name = request.data.get('family_name')
        variant_code = request.data.get('variant_code')
        golden_list = request.data.get('goldens', [])

        if not all([family_name, variant_code, isinstance(golden_list, list)]):
            return Response({"error": "Wymagane pola: family_name, variant_code, goldens (jako lista)."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            family = ProductFamily.objects.get(name=family_name)
        except ProductFamily.DoesNotExist:
            return Response({"error": f"Brak rodziny o nazwie '{family_name}'."},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            variant = VariantCode.objects.get(product_family=family, code=variant_code)
        except VariantCode.DoesNotExist:
            return Response({"error": f"Brak wariantu '{variant_code}' w rodzinie '{family_name}'."},
                            status=status.HTTP_404_NOT_FOUND)

        db_goldens = set(
            GoldenSampleCode.objects.filter(variant_code=variant)
            .values_list('sample_code', flat=True)
        )

        result = {code: (code in db_goldens) for code in golden_list}
        return Response(result)