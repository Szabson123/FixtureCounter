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
                status=status.HTTP_200_OK
            )
        
        return Response(
                {"returnCodeDescription": "Machine Valid",
                 "returnCode": 200},
                status=status.HTTP_200_OK
            )


class CheckGoldensFWK(GenericAPIView):
    serializer_class = CheckMasterSampleFWK

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        sn = data['sn']
        result = data['result']
        machine = data['machine_id']
        site = data['site']
        internal_code = data['internal_code']

        timer_obj, _ = EndCodeTimeFWK.objects.get_or_create(machine_id=machine, site=site, endcode=internal_code)

        try:
            temp_set = TempMasterShow.objects.get(machine_id=machine, site=site, if_set=True)
            master = MasterSample.objects.select_related('master_type').filter(sn=temp_set.sn).first()
            last = LastResultFWK.objects.filter(machine_id=machine, site=site).order_by('-date_time_tested').first()

            # Backtaking logic:
            # Master verifies previous test -> compare current master result type with previous test result
            if master and last and master.master_type.compute_name.lower() == result:
                check, _ = TempCheckMasterFWK.objects.get_or_create(machine_id=machine, site=site)
                mt = master.master_type.compute_name.lower()
                if mt == 'pass':
                    check.pass_res = True
                elif mt == 'fail':
                    check.fail_res = True
                check.save()

                if check.pass_res and check.fail_res:
                    timer_obj.last_good_tested = timezone.now()
                    timer_obj.save()

                    check.pass_res = False
                    check.fail_res = False
                    check.save()
                    temp_set.if_set = False
                    temp_set.save()

        except TempMasterShow.DoesNotExist:
            pass
        
        master_for_sn = MasterSample.objects.filter(sn=sn).first()
        if master_for_sn:
            has_code = master_for_sn.endcodes.filter(code=internal_code).exists()

            if has_code:
                temp_obj, _ = TempMasterShow.objects.get_or_create(machine_id=machine, site=site)
                temp_obj.if_set = True
                temp_obj.sn = sn
                temp_obj.save()
        if not master_for_sn:
            try:
                temp_obj_non = TempMasterShow.objects.get(machine_id=machine, site=site)
                temp_obj_non.if_set = False
                temp_obj_non.save()
            except:
                ...

        LastResultFWK.objects.create(
            sn=sn,
            result=result.lower() if result else None,
            machine_id=machine,
            site=site
        )

        if master_for_sn:
            return Response({"comment": "Testujesz Wzorca",
                             "result": True}, status=status.HTTP_200_OK)

        last_good = getattr(timer_obj, 'last_good_tested', None)
        last_endcode = getattr(timer_obj, 'endcode', None)

        if not last_good:
            return Response({"comment": "Nalezy przetestowac wzorce [minelo wiecej niz 8godzin]",
                             "result": False}, status=status.HTTP_200_OK)
        
        if not last_endcode or last_endcode != internal_code:
            return Response({"comment": "Nalezy przetestowac wzorce [zmiana 'internal code']",
                    "result": False}, status=status.HTTP_200_OK)

        time_diff = timezone.now() - last_good
        if time_diff > timedelta(hours=8):
            return Response({"comment": "Nalezy przetestowac wzorce [minelo wiecej niz 8godzin]",
                             "result": False}, status=status.HTTP_200_OK)
        
        return Response({"comment": "Pass",
                        "result": True}, status=status.HTTP_200_OK)



        
        

