from .models import *
from .serializers import *
from .utils import gen_code
from rest_framework.generics import ListAPIView
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.response import Response
from rest_framework import viewsets, status, filters, generics
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import GenericAPIView

from django.utils.timezone import now
from datetime import date, datetime

import json


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
        group_code = str(sn[12:]).strip()

        variant = VariantCode.objects.filter(code=variant_code).first()

        if variant:
            if not variant.group:
                group, _ = GroupVariantCode.objects.get_or_create(name=group_code)
                variant.group = group
                variant.save()
            elif variant.group.name.strip().lower() != group_code.lower():
                return Response({
                    "error": "Kod SN nie pasuje do grupy przypisanej do tego wariantu.",
                    "expected_group": variant.group.name,
                    "sn_group": group_code
                }, status=status.HTTP_400_BAD_REQUEST)
            
        else:
            group, _ = GroupVariantCode.objects.get_or_create(name=group_code)
            variant = VariantCode.objects.create(
                code=variant_code,
                group=group,
                name=variant_name
            )

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
            expire_date=expire_date or None
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
                {"error": "Nie wszystkie SN-y należą do tej samej grupy."},
                status=status.HTTP_400_BAD_REQUEST
            )

        group_code = group_codes.pop()

        try:
            group = GroupVariantCode.objects.get(name=group_code)
        except GroupVariantCode.DoesNotExist:
            return Response({"error": "Podana grupa nie istnieje."}, status=status.HTTP_400_BAD_REQUEST)

        variants_in_group = VariantCode.objects.filter(group=group)
        today = date.today()
        results = {}

        for sn in sn_list:
            sample = GoldenSample.objects.filter(
                golden_code=sn,
                variant__in=variants_in_group
            ).first()

            if sample and sample.expire_date and sample.expire_date > today:
                results[sn] = True
            else:
                results[sn] = False
                
        group.last_time_tested = now()
        group.save()
          
        return Response({"result": results}, status=status.HTTP_200_OK)
        

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
    

STATUS_TO_TYPE = {
    "WZORZEC ZGODNY": "good",
    "WZORZEC NIEZGODNY": "bad",
    "WZORZEC KALIBARCYJNY": "calib"
}

class GoldenSampleBulkUploadView(APIView):
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "Brak pliku."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = json.load(file)
        except Exception as e:
            return Response({"error": f"Błąd przy odczycie pliku JSON: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        created_samples = []
        errors = []

        for row in data:
            firma = str(row.get('firma', '')).strip()
            model = str(row.get('model', '')).strip()
            numer = str(row.get('numer', '')).strip()
            variant_code = numer
            variant_name = f"{firma}-{model}"
            kody = row.get('kody', [])
            status_str = row.get('status', '').strip().upper()
            expire_str = row.get('data', '').strip()

            type_golden = STATUS_TO_TYPE.get(status_str)
            if not type_golden:
                errors.append(f"Nieznany status: {status_str}")
                continue

            try:
                expire_date = datetime.strptime(expire_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append(f"Nieprawidłowa data: {expire_str}")
                continue

            for sn in kody:
                sn = sn.strip()
                if len(sn) < 13:
                    errors.append(f"SN za krótki: {sn}")
                    continue

                group_code = sn[12:].strip()
                variant = VariantCode.objects.filter(code=variant_code).first()

                if variant:
                    if not variant.group:
                        group, _ = GroupVariantCode.objects.get_or_create(name=group_code)
                        variant.group = group
                        variant.save()
                    elif variant.group.name.strip().lower() != group_code.lower():
                        errors.append(f"Grupa SN ({group_code}) nie pasuje do wariantu ({variant.group.name})")
                        continue
                else:
                    group, _ = GroupVariantCode.objects.get_or_create(name=group_code)
                    variant = VariantCode.objects.create(
                        code=variant_code,
                        name=variant_name,
                        group=group
                    )

                if GoldenSample.objects.filter(golden_code=sn, variant=variant).exists():
                    continue

                golden_sample = GoldenSample.objects.create(
                    variant=variant,
                    golden_code=sn,
                    type_golden=type_golden,
                    expire_date=expire_date
                )

                CounterOnGolden.objects.create(
                    golden_sample=golden_sample,
                    counter=0
                )

                created_samples.append(golden_sample.id)

        return Response({
            "utworzono": len(created_samples),
            "błędy": errors
        }, status=status.HTTP_201_CREATED if created_samples else status.HTTP_400_BAD_REQUEST)
        

class GoldenSampleVariantList(viewsets.ModelViewSet):
    serializer_class = GoldenSampleSimpleSerializer
    queryset = GoldenSample.objects.all()
    
    def get_queryset(self):
        variant = self.kwargs.get('variant_id')
        queryset = GoldenSample.objects.filter(variant=variant)
        return queryset
    
    def create(self, request, *args, **kwargs):
        return Response(
            {"error": "Tworzenie GoldenSample nie jest dozwolone w tym widoku."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


class VariantListView(viewsets.ModelViewSet):
    queryset = VariantCode.objects.all()
    serializer_class = VariantShortSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['code']
    ordering = ['code']
    search_fields = ['code', 'name']


class GoldenSamplePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100
    

class GoldenSampleAdminView(viewsets.ModelViewSet):
    queryset = GoldenSample.objects.all().select_related('counterongolden')
    serializer_class = GoldenSampleDetailedSerializer
    pagination_class = GoldenSamplePagination
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['expire_date']
    ordering = ['expire_date']
    search_fields = ['golden_code']

    def create(self, request, *args, **kwargs):
        return Response(
            {"error": "Tworzenie GoldenSample nie jest dozwolone w tym widoku."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
        

class GoldenSampleBinChecker(APIView):
    def post(self, request, *args, **kwargs):
        endpoint_input = request.data.get('code')
        
        if not endpoint_input:
            return Response({'error': 'Missing "code" in request data.'}, status=status.HTTP_400_BAD_REQUEST)
        
        obj = MapSample.objects.filter(i_input=endpoint_input).first()
        
        output_value = obj.i_output if obj else ""

        return Response({
            'output': output_value
        }, status=status.HTTP_200_OK)
        

class GoldenSampleBinAdder(APIView):
    def post(self, request, *args, **kwargs):
        endpoint_input = request.data.get('code')
        endpoint_input2 = request.data.get('site_code')
        
        if not endpoint_input or not endpoint_input2:
            return Response({'error': 'Missing "code" or "site_code" in request data.'}, status=status.HTTP_400_BAD_REQUEST)
        
        obj, created = MapSample.objects.get_or_create(
            i_input=endpoint_input,
            i_output=endpoint_input2
        )
        
        return Response({
            'id': obj.id,
            'i_input': obj.i_input,
            'i_output': obj.i_output,
            'created': created
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    

class AddEventSn(GenericAPIView):
    serializer_class = PcbEventSerializer

    def post(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        instances = ser.save()
        
        return Response(
            [{"sn": obj.sn, "result": obj.result, "shared_plate": obj.shared_plate} for obj in instances],
            status=status.HTTP_201_CREATED
        )


class CheckEventSn(GenericAPIView):
    serializer_class = PcbEventSerializerCheck

    def post(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        sn = ser.validated_data["sn"]

        obj = PcbEvent.objects.filter(sn=sn).order_by("-time_date_tested").first()
        if not obj or not obj.shared_plate:
            return Response({"result": False}, status=status.HTTP_200_OK)

        code = obj.shared_plate

        if PcbEvent.objects.filter(shared_plate=code, result=False).exists():
            return Response({"result": False}, status=status.HTTP_200_OK)

        if PcbEvent.objects.filter(shared_plate=code, result=True).exists():
            return Response({"result": True}, status=status.HTTP_200_OK)

        return Response({"result": False}, status=status.HTTP_200_OK)
    

@extend_schema_view(
    list=extend_schema(
        tags=["MasterSample"]
    )
)
class MasterSampleListView(ListAPIView):
    queryset = MasterSample.objects.all().select_related(
        "client", "process_name", "master_type", "created_by"
    )
    serializer_class = MasterSampleSerializerList