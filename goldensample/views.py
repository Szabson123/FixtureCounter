from .models import *
from .serializers import *
from .filters import MasterSampleFilter
from rest_framework.generics import ListAPIView, CreateAPIView
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.response import Response
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import GenericAPIView, RetrieveUpdateAPIView

from django_filters.rest_framework import DjangoFilterBackend

from django.utils.timezone import now
from django.utils import timezone
from datetime import date
from datetime import timedelta

        
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
    

class MasterSamplePagination(PageNumberPagination):
    page_size = 20
    max_page_size = 100


class MasterSampleListView(ListAPIView):
    queryset = (MasterSample.objects.select_related("client", "process_name", "master_type", "created_by", "departament",).prefetch_related("endcodes","code_smd",))
    serializer_class = MasterSampleSerializerList
    pagination_class = MasterSamplePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['sn', 'pcb_rev_code', 'client', 'process_name', 'departament']
    search_fields = ['project_name', 'sn', 'pcb_rev_code', 'client__name', 'master_type__name', 'created_by__first_name', 'created_by__last_name', 'departament__name']
    ordering_fields = ['id', 'client__name', 'project_name', 'process_name__name', 'sn', 'master_type__name', 'date_created', 'expire_date', 'pcb_rev_code', 'departament__name', 'created_by__last_name']
    filterset_class = MasterSampleFilter


class ClientNameViewSet(viewsets.ModelViewSet):
    queryset = ClientName.objects.all()
    serializer_class = ClientNameSerializer

class ProcessNameViewSet(viewsets.ModelViewSet):
    queryset = ProcessName.objects.all()
    serializer_class = ProcessNameSerializer

class TypeNameViewSet(viewsets.ModelViewSet):
    queryset = TypeName.objects.all()
    serializer_class = TypeNameSerializer

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

class CodeSmdViewSet(viewsets.ModelViewSet):
    queryset = CodeSmd.objects.all()
    serializer_class = CodeSmdSerializer

class EndCodeViewSet(viewsets.ModelViewSet):
    queryset = EndCode.objects.all()
    serializer_class = CodeSmdSerializer

# -----------------------------------------------------------------------

class MasterSampleCreateView(CreateAPIView):
    queryset = MasterSample.objects.all()
    serializer_class = MasterSampleManyCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        masters = serializer.save()
        output = MasterSampleSerializerList(masters, many=True)
        return Response(output.data, status=status.HTTP_201_CREATED)


class MasterSampleRetrieveUpdateView(RetrieveUpdateAPIView):
    queryset = MasterSample.objects.all()
    serializer_class = MasterSampleUpdateSerializer
    http_method_names = ["get", "patch", "put"]

    def update(self, request, *args, **kwargs):
        partial = request.method.lower() == "patch"
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(MasterSampleSerializerList(instance).data)
    

class MachineTimeStampView(GenericAPIView):
    serializer_class = MachineTimeStampSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        machine_name = serializer.validated_data['machine_name']

        machine, created = MachineGoldensTime.objects.get_or_create(
            machine_name=machine_name,
            defaults={'date_time': timezone.now()},
        )

        if created:

            return Response(
                {"returnCodeDescription": "Machine Valid",
                 "returnCode": 200},
                status=status.HTTP_200_OK
            )
        
        time_diff = timezone.now() - machine.date_time

        if time_diff > timedelta(hours=8):
            return Response(
                {"returnCodeDescription": "Machine Block",
                 "returnCode": 123},
                status=status.HTTP_423_LOCKED
            )
        
        return Response(
                {"returnCodeDescription": "Machine Valid",
                 "returnCode": 200},
                status=status.HTTP_200_OK
            )