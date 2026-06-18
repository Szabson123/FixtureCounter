import httpx
import threading
from datetime import timedelta

from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from .services import SetGoodOrderService, CreateGoldensToTypeCheck
from .serializers import GoldensMainValidationSerializer, ProductionObserverSerializer, GoldensTypeValidationSerializer, ForceValidMachineSerializer, MachineInvalidate
from .models import FullValidationMachineModel, Machine, TestedSn, EndedCodesWithQueue, GoldenTypeValidate, TaskNum, ForceValidMachine
from goldensample.models import MasterSample


port = settings.SPEA_MICRO_SERVICE_PORT
service_name = settings.SPEA_MICRO_SERVICE_NAME

def send_requests_worker(port, service_name, bins_payload, phase_payload):
    with httpx.Client() as client:
        try:
            client.post(f"http://127.0.0.1:{port}/{service_name}/check-bins/", json=bins_payload)
            client.post(f"http://127.0.0.1:{port}/{service_name}/check-phase/", json=phase_payload)
        except Exception as e:
            print(e)


class GoldensPrepareCheck(GenericAPIView):
    serializer_class = GoldensMainValidationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phase_id = serializer.validated_data['phase_id']
        goldens = serializer.validated_data['goldens']
        machine_name = serializer.validated_data['machine_name']
        unique_id = serializer.validated_data.get('unique_id')

        machine = get_object_or_404(Machine, name=machine_name)

        if unique_id:
            try:
                full_model = FullValidationMachineModel.objects.get(unique_id=unique_id, ended=False)
            except:
                return Response({"error": f"there is no full validation model like: {unique_id}"})
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

        # Zdobycie modelu do pozniejszej analizy

        full_model = FullValidationMachineModel.objects.prefetch_related('typesvalidate').filter(machine__name=machine_name, ended=False).first()

        print(full_model)

        type_dict = {
            'pass': 'Dobry',
            'calib': 'Kalibracyjny',
            'fail': 'Zły'
        }

        # Ustawiania odpowiednich wzorców jako pasy i faile 

        if full_model:
            prefetch_types = list(full_model.typesvalidate.all())
            for index, (golden_key, golden_value) in enumerate(goldens.items(), start=1):
                expected_type = type_dict.get(golden_value)
                sample_exists = MasterSample.objects.filter(sn=golden_key, master_type__name=expected_type).exists()

                if sample_exists:
                    types = next((t for t in prefetch_types if t.side==index), None)
                    if types:
                        if expected_type in ['Dobry', 'Kalibracyjny']:
                            types.good_golden = True
                        elif expected_type == 'Zły':
                            types.bad_golden = True
                        types.save()
                else:
                    continue
        else:
            return Response({"error": "You try ask for types of goldens before put them into spea"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Sprawdzenie czy maszyna jest już zwalidowana
        
        fully_validated_types = [
            t for t in prefetch_types
            if t.good_golden is True and t.bad_golden is True
        ]
        
        if len(prefetch_types) == len(fully_validated_types):
            full_model.ended = True
            full_model.is_valid = True
            full_model.save()
            return Response({"status": "completed", "message": "All sides have been validated"}, status=status.HTTP_200_OK)
        
        # Maszyna nie zwalidowana wyświetlamy mapę czego brakuje
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

        sns = serializer.validated_data['sns']
        machine_name = serializer.validated_data['machine_name']
        phase_id = serializer.validated_data['phase_id']

        machine = get_object_or_404(Machine, name=machine_name)

        # Z listy sn utworzyć batchem instancje TestedSn
        tested_sn_objects = [
            TestedSn(sn=sn, bin={}, prev_phase=False, machine=machine)
            for sn in sns
        ]

        TestedSn.objects.bulk_create(tested_sn_objects)

        # Przypisanie sn w odpowiedniej kolejności do phase_id

        full_validation = FullValidationMachineModel.objects.filter(machine__name=machine_name).first()
        prepared_sns = {}
        sn_with_codes = {}
        for index, sn in enumerate(sns, start=1):
            endcode = EndedCodesWithQueue.objects.filter(
                full_validation=full_validation, 
                queue=index
            ).values_list('code', flat=True).first()

            sn_with_codes[sn] = str(endcode) if endcode else ""

        # wywołanie serwisu sprawdzenia poprzedniej fazy (fire and forget)
        # przesyłamy listę sn, machine_name

        # wywołanie serwisu ustawienia binów (fire and forget)
        # przesyłamy listę sn, machine_name

        task_num = TaskNum.objects.create()

        phase_payload = {
            "sns": sn_with_codes,
            "machine_name": str(machine_name),
            "phase_id": str(phase_id),
            "task_num": str(task_num.unique_id)
        }

        bins_payload = {
            "machine_name": machine_name,
            "sns": sns,
            "task_num": str(task_num.unique_id)
        }

        t = threading.Thread(
                target=send_requests_worker, 
                args=(port, service_name, bins_payload, phase_payload)
            )
        t.start()

        # Zwrotka tylko że przyjęte, 202 Accepted
        return Response({"status": "accepted", "message": "Batch initialized", "task_num": f"{task_num.unique_id}"}, status=status.HTTP_202_ACCEPTED)


class ForceValidateMachine(GenericAPIView):
    serializer_class = ForceValidMachineSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        machine_name = serializer.validated_data['machine_name']
        hours = serializer.validated_data['hours']
        
        machine = get_object_or_404(Machine, name=machine_name)
        
        ForceValidMachine.objects.create(
            machine=machine,
            date_time_end = timezone.now() + timedelta(hours=hours)
        )

        return Response({"success": f"Machine: {machine.name} has been valdiated for {hours}h"}, status=status.HTTP_200_OK)
    

class InValidateMachine(GenericAPIView):
    serializer_class = MachineInvalidate

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        machine_name = serializer.validated_data['machine_name']
        machine = get_object_or_404(Machine, name=machine_name)

        ForceValidMachine.objects.filter(machine=machine).update(is_valid=False)
        FullValidationMachineModel.objects.filter(machine=machine).update(is_valid=False)

        return Response({"success": f"Machine: {machine.name} has been invalidated"}, status=status.HTTP_200_OK)