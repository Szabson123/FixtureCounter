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


class MasterSampleCheckView(GenericAPIView):
    serializer_class = MasterSampleCheckSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        machine_name = serializer.validated_data['machine_name']
        goldens = serializer.validated_data['goldens']

        machine = MachineGoldensTime.objects.filter(machine_name=machine_name).first()

        if not machine:
            return Response(
                {"returnCodeDescription": "Machine doesn't exist",
                 "returnCode": 400},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        results = {}

        for golden in goldens:
            sample = MasterSample.objects.filter(sn=golden).first()

            if sample and sample.expire_date and sample.expire_date > today:
                results[golden] = True
            else:
                results[golden] = False
        
        if all(results.values()):
            machine.date_time = timezone.now()
            machine.save()
        
        return Response({"result": results}, status=status.HTTP_200_OK)
    

class MasterSampleTypeCheck(GenericAPIView):
    serializer_class = MasterSampleTypeSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        goldens = serializer.validated_data['goldens']
        results = {}

        for golden in goldens:
            sample = MasterSample.objects.filter(sn=golden).first()

            if sample:
                sample.counter += 1
                sample.save()

                eng_dic = {
                        'Zły': 'Bad',
                        'Dobry': 'Good',
                        'Kalibracyjny': 'Calib'
                    }
                res = eng_dic.get(sample.master_type.name, 'Unknown')

                results[golden] = res
            else:
                results[golden] = False
        
        return Response({"result": results}, status=status.HTTP_200_OK)

         
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
    queryset = (MasterSample.objects
                .select_related("client", "process_name", "master_type", "created_by", "departament",)
                .prefetch_related("endcodes","code_smd",)
                .order_by('-id'))
    serializer_class = MasterSampleSerializerList
    pagination_class = MasterSamplePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['sn', 'pcb_rev_code', 'client', 'process_name', 'departament']
    search_fields = ['project_name', 'sn', 'pcb_rev_code', 'client__name', 'master_type__name', 'created_by__first_name', 'created_by__last_name', 'departament__name', 'endcodes__code', 'code_smd__code']
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
    

class FromGoldensToMasters(APIView):
    def post(self, request, *args, **kwargs):
        goldens = GoldenSample.objects.all()

        # przygotuj stałe wartości (żeby nie tworzyć w kółko)
        process, _ = ProcessName.objects.get_or_create(name="SMT")
        dep, _ = Department.objects.get_or_create(name="SMD")

        # mapowanie typu goldena -> typu mastera
        type_map = {
            "good": "Dobry",
            "bad": "Zły",
            "calib": "Kalibracyjny",
        }

        created = []
        for golden in goldens:
            variant = golden.variant
            variant_name = variant.name or ""
            variant_code = variant.code or ""

            master_type_name = type_map.get(golden.type_golden, "Nieznany")
            master_type, _ = TypeName.objects.get_or_create(name=master_type_name)

            endcode_list = []
            if "/" in variant_code:
                base, suffix = variant_code.split("/")
                base = base.strip()
                suffix = suffix.strip()
                if len(base) >= 8:
                    prefix = base[:-2]
                    start = base[-2:]
                    end = suffix
                    try:
                        first_num = int(start)
                        second_num = int(end)
                        endcode_list = [f"{prefix}{first_num:02d}", f"{prefix}{second_num:02d}"]
                    except ValueError:
                        endcode_list = [base, suffix]
                else:
                    endcode_list = [base, suffix]
            else:
                endcode_list = [variant_code.strip()]

            endcodes = [EndCode.objects.get_or_create(code=code)[0] for code in endcode_list if code]

            code_smd_value = golden.golden_code[-8:] if golden.golden_code else None
            code_smd_obj = None
            if code_smd_value:
                code_smd_obj, _ = CodeSmd.objects.get_or_create(code=code_smd_value)

            master = MasterSample.objects.create(
                sn=golden.golden_code,
                date_created=golden.expire_date - timedelta(days=365),
                expire_date=golden.expire_date,
                project_name=variant_name,
                process_name=process,
                departament=dep,
                master_type=master_type,
                pcb_rev_code="",
                counter=0,
            )

            if code_smd_obj:
                master.code_smd.add(code_smd_obj)
            if endcodes:
                master.endcodes.add(*endcodes)

            created.append(master.sn)

        return Response(
            {"created_masters": created, "count": len(created)},
            status=status.HTTP_201_CREATED
        )
