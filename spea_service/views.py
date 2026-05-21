from django.shortcuts import render
from django.utils import timezone
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from .services import SetGoodOrderService
from .serializers import GoldensMainValidationSerializer
from .models import FullValidationMachineModel, Machine


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
            date=timezone.now()
        )

        set_good_order = SetGoodOrderService(full_model, **serializer.validated_data)
        set_good_order.prepare_end_codes_in_queue()

        full_model.is_valid = True # Ask team member set True here or later
        full_model.save()

        return Response({"success": "Goldens are correct"})


class ProductionObserverSerwice(GenericAPIView):
    serializer_class = ...

    def post(self, request, *args, **kwargs):
        # Utworzenie UniqueTestValue

        # Z listy sn utworzyć batchem instancje TestedSn

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