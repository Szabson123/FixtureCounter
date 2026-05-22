from django.shortcuts import render
from django.utils import timezone

from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from .services import SetGoodOrderService, CreateGoldensToTypeCheck
from .serializers import GoldensMainValidationSerializer, ProductionObserverSerializer, GoldensTypeValidationSerializer
from .models import FullValidationMachineModel, Machine, UniqueTestValue, TestedSn, EndedCodesWithQueue


class GoldensPrepareCheck(GenericAPIView):
    serializer_class = GoldensMainValidationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phase_id = serializer.validated_data['phase_id']
        goldens = serializer.validated_data['goldens']
        machine_name = serializer.validated_data['machine_name']

        try:
            machine = Machine.objects.get(name=machine_name)
        except Machine.DoesNotExist:
            raise serializers.ValidationError({"error": f"{value} - does not exist in database please contact IT dept"})

        full_model = FullValidationMachineModel.objects.create(
            machine=machine,
            is_valid=False,
            time_date=timezone.now()
        )

        set_good_order = SetGoodOrderService(full_model, **serializer.validated_data)
        set_good_order.prepare_end_codes_in_queue()

        create_goldens = CreateGoldensToTypeCheck(full_model, goldens)
        create_goldens.create_goldens_to_type_check()

        return Response({"success": "Goldens are correct"})
    

class GoldenTypeCheck(GenericAPIView):
    serializer_class = GoldensTypeValidationSerializer
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)


class ProductionObserverService(GenericAPIView):
    serializer_class = ProductionObserverSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Utworzenie UniqueTestValue
        unique_test = UniqueTestValue.objects.create()

        goldens = serializer.validated_data['goldens']
        machine_name = serializer.validated_data['machine']

        # Z listy sn utworzyć batchem instancje TestedSn
        tested_sn_objects = [
            TestedSn(test_num=unique_test, sn=golden, bin={}, prev_phase=False)
            for golden in goldens
        ]

        TestedSn.objects.bulk_create(tested_sn_objects)

        # Pzypisanie sn w odpwienidej kolejnosci do phase_id

        full_validation = FullValidationMachineModel.objects.filter(machine__name=machine_name).first()

        prepared_golden = {}

        for index, golden in enumerate(goldens, start=1):
            endcode = EndedCodesWithQueue.objects.filter(full_validation=full_validation, queue=index).values_list('code', flat=True).first()

            prepared_golden[golden] = endcode
        
        # wywołanie serwisu sprawdzenia poprzedniej fazy (fire and forget)
        # przesyłamy listę sn

        # wywołanie serwisu ustawienia binów (fire and forget)
        # przesyłamy listę sn

        # Zwotka tylko że przyjęte, 202 Accepted
        ...


class ProductionCheckValidation(GenericAPIView):
    serializer_class = ...

    def post(self, request, *args, **kwargs):
        # Sprawdzenie czy ta maszyna może produkować -> FullValidationMachineModel
        ...