from .models import *
from .serializers import *

from rest_framework.response import Response
from rest_framework import viewsets, status, filters, generics
from rest_framework.views import APIView

from datetime import date


class GoldenSampleCreateView(APIView):
    def post(self, request):
        serializer = GoldenSampleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        sn = data['sn']
        type_golden = data['type_golden']
        variant_code = data['variant_code']
        variant_name = data.get('variant_name')
        expire_date = data.get('expire_date')

        if len(sn) < 13:
            return Response({"error": "SN za krótki"}, status=status.HTTP_400_BAD_REQUEST)

        golden_code = sn
        group_code = sn[12:]

        group, _ = GroupVariantCode.objects.get_or_create(name=group_code)
        
        if VariantCode.objects.filter(code=variant_code, group=group).exists():
            return Response({
                "error": "VariantCode już istnieje w tej grupie"
            }, status=status.HTTP_400_BAD_REQUEST)

        variant, created = VariantCode.objects.get_or_create(code=variant_code, group=group)

        if created and variant_name:
            variant.name = variant_name
            variant.save()

        existing = GoldenSample.objects.filter(golden_code=golden_code, variant=variant).first()
        if existing:
            return Response({
                "message": "GoldenSample już istnieje",
                "id": existing.id
            }, status=status.HTTP_200_OK)

        golden_sample = GoldenSample.objects.create(
            variant=variant,
            golden_code=golden_code,
            type_golden=type_golden,
            expire_date=expire_date if expire_date else None
        )
        
        counter = CounterOnGolden.objects.create(
            golden_sample=golden_sample,
            counter=0
        )

        return Response({
            "message": "GoldenSample utworzony",
            "id": golden_sample.id,
            "golden_code": golden_sample.golden_code,
            "type": golden_sample.type_golden,
            "counter": counter.counter
        }, status=status.HTTP_201_CREATED)
        
        
class GoldenSampleCheckView(APIView):
    def post(self, request):
        serializer = GoldenSampleCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sn_list = serializer.validated_data['goldens']

        if not sn_list:
            return Response({"error": "Lista SN-ów jest pusta."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            group_codes = {sn[12:] for sn in sn_list if len(sn) >= 13}
        except Exception:
            return Response({"error": "Niepoprawny format SN."}, status=status.HTTP_400_BAD_REQUEST)

        if len(group_codes) != 1:
            return Response(
                {"error": "Nie wszystkie goldeny należą do tej samej grupy."},
                status=status.HTTP_400_BAD_REQUEST
            )

        group_code = group_codes.pop()

        try:
            group = GroupVariantCode.objects.get(name=group_code)
        except GroupVariantCode.DoesNotExist:
            return Response({"error": "Podana grupa nie istnieje."}, status=status.HTTP_400_BAD_REQUEST)

        variants = VariantCode.objects.filter(group=group)
        results = {}

        for sn in sn_list:
            if len(sn) < 20:
                results[sn] = False
                continue

            sample = GoldenSample.objects.filter(
                golden_code=sn,
                variant__in=variants
            ).first()

            if sample and sample.expire_date and sample.expire_date > date.today():
                results[sn] = True
            else:
                results[sn] = False

        return Response({
            "result": results
        }, status=status.HTTP_200_OK)
        

class GroupFullListView(generics.ListAPIView):
    queryset = VariantCode.objects.all().select_related('group').prefetch_related('goldensample_set')
    serializer_class = VariantFullSerializer

    filter_backends = [filters.SearchFilter]
    search_fields = ['code', 'name']
    
    
class GoldenSampleTypeCheckView(APIView):
    def post(self, request):
        serializer = GoldenSampleCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sn_list = serializer.validated_data['goldens']

        results = {}

        for sn in sn_list:
            sample = GoldenSample.objects.filter(golden_code=sn).first()
            
            if sample:
                try:
                    counter = sample.counterongolden
                    counter.counter += 1
                    counter.save()
                except CounterOnGolden.DoesNotExist:
                    CounterOnGolden.objects.create(golden_sample=sample, counter=1)

                results[sn] = sample.type_golden
            else:
                results[sn] = None

        return Response({"result": results}, status=status.HTTP_200_OK)
    

class GoldenSampleAdminView(viewsets.ModelViewSet):
    queryset = GoldenSample.objects.all().select_related('counterongolden')
    serializer_class = GoldenSampleDetailedSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['expire_date']
    ordering = ['expire_date']

    def create(self, request, *args, **kwargs):
        return Response(
            {"error": "Tworzenie GoldenSample nie jest dozwolone w tym widoku."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )