from django.shortcuts import render
from django.utils import timezone

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from .services import SetGoodOrderService, CreateGoldensToTypeCheck
from .serializers import GoldensMainValidationSerializer, ProductionObserverSerializer, GoldensTypeValidationSerializer
from .models import FullValidationMachineModel, Machine, UniqueTestValue, TestedSn, EndedCodesWithQueue, GoldenTypeValidate
from goldensample.models import MasterSample

class GoldensPrepareCheck(GenericAPIView):
    serializer_class = GoldensMainValidationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phase_id = serializer.validated_data['phase_id']
        goldens = serializer.validated_data['goldens']
        machine_name = serializer.validated_data['machine_name']
        unique_id = serializer.validated_data['unique_id']

        try:
            machine = Machine.objects.get(name=machine_name)
        except Machine.DoesNotExist:
            raise serializers.ValidationError({"error": f"{value} - does not exist in database please contact IT dept"})

        if unique_id:
            try:
                full_model = FullValidationMachineModel.objects.get(unique_id=unique_id, end=False)
            except:
                return Response({"error": f"there is no full validation modal like: {unique_id}"})
        else:
            full_model = FullValidationMachineModel.objects.create(
                machine=machine,
                is_valid=False,
                time_date=timezone.now()
            )

        set_good_order = SetGoodOrderService(full_model, **serializer.validated_data)
        set_good_order.prepare_end_codes_in_queue()

        create_goldens = CreateGoldensToTypeCheck(full_model, goldens)
        create_goldens.create_goldens_to_type_check()

        return Response({"success": "Goldens are correct", "unique_id": full_model.unique_id})
    

class GoldenTypeCheck(GenericAPIView):
    serializer_class = GoldensTypeValidationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        goldens = serializer.validated_data['goldens']
        machine_name = serializer.validated_data['machine_name']

        full_model = FullValidationMachineModel.objects.prefetch_related('typesvalidate').filter(machine__name=machine_name, ended=False).first()

        print(full_model)

        type_dict = {
            'pass': 'Dobry',
            'fail': 'Zły'
        }

        if full_model:
            prefetch_types = list(full_model.typesvalidate.all())
            for index, (golden_key, golden_value) in enumerate(goldens.items(), start=1):
                expected_type = type_dict.get(golden_value)
                sample_exists = MasterSample.objects.filter(sn=golden_key, master_type__name=expected_type).exists()

                if sample_exists:
                    types = next((t for t in prefetch_types if t.side==index), None)
                    if types:
                        if expected_type == 'Dobry':
                            types.good_golden = True
                        elif expected_type == 'Zły':
                            types.bad_golden = True
                        types.save()
                else:
                    continue
        else:
            return Response({"error": "You try ask for types of goldens before put them into spea"}, status=status.HTTP_400_BAD_REQUEST)
        
        fully_validated_types = [
            t for t in prefetch_types
            if t.good_golden is True and t.bad_golden is True
        ]
        
        if len(prefetch_types) == len(fully_validated_types):
            full_model.ended = True
            full_model.save()
            return Response({"status": "completed", "message": "All sides have been validated"}, status=status.HTTP_200_OK)
        
        else:
            validation_map = {}
            for t in prefetch_types:
                validation_map[f"side_{t.side}"] = {
                    "good_golden": t.good_golden,
                    "bad_golden": t.bad_golden
                }
            return Response({"status": "incomplete", "message": "Machine not fully validated", "map": validation_map}, status=status.HTTP_200_OK)
        

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