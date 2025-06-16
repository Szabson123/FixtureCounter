from rest_framework import viewsets, status

from django.shortcuts import get_object_or_404, get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db import transaction

from .models import Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place
from .serializers import ProductSerializer, ProductProcessSerializer, ProductObjectSerializer, ProductObjectProcessSerializer, ProductObjectProcessLogSerializer, PlaceSerializer, ProductMoveSerializer, ProductReceiveSerializer

from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from .filters import ProductObjectFilter
from .utils import parse_full_sn

from datetime import timedelta
from django.utils.timezone import now


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class ProductProcessViewSet(viewsets.ModelViewSet):
    serializer_class = ProductProcessSerializer

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductProcess.objects.filter(product_id=product_id)

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, pk=product_id)
        serializer.save(product=product)
        

class PlaceViewSet(viewsets.ModelViewSet):
    serializer_class = PlaceSerializer
    
    def get_queryset(self):
        process_id = self.kwargs.get('process_id')
        return Place.objects.filter(process=process_id)
    
    def perform_create(self, serializer):
        process_id = self.kwargs.get('process_id')
        process = get_object_or_404(ProductProcess, pk=process_id)
        serializer.save(process=process)


class ProductObjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProductObjectSerializer
    
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductObjectFilter
    
    ordering_fields = ['created_at', 'serial_number', 'current_process', 'current_place']
    ordering = ['-created_at']

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductObject.objects.filter(product_id=product_id)


    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, pk=product_id)

        place_name = serializer.validated_data.pop('place_name', None)
        who_entry = serializer.validated_data.pop('who_entry', None)
        full_sn = serializer.validated_data.get('full_sn')

        if not place_name or not who_entry or not full_sn:
            raise ValidationError("Brakuje 'place', 'who_entry' lub 'full_sn' w danych.")

        try:
            serial_number, production_date, expire_date = parse_full_sn(full_sn)
        except ValueError as e:
            raise ValidationError(str(e))

        with transaction.atomic():
            place_obj, _ = Place.objects.get_or_create(name=place_name)

            serializer.validated_data['serial_number'] = serial_number
            serializer.validated_data['production_date'] = production_date
            serializer.validated_data['expire_date'] = expire_date
            serializer.validated_data['product'] = product

            product_object = serializer.save()

            processes = list(ProductProcess.objects.filter(product=product).order_by('order'))
            first_process = processes[0] if processes else None

            product_object.current_process = first_process
            product_object.current_place = place_obj
            product_object.save()

            for process in processes:
                po_process = ProductObjectProcess.objects.create(
                    product_object=product_object,
                    process=process,
                    is_completed=False
                )

                if process == first_process:
                    ProductObjectProcessLog.objects.create(
                        product_object_process=po_process,
                        who_entry=who_entry,
                        place=place_obj
                    )


class ProductObjectProcessViewSet(viewsets.ModelViewSet):
    serializer_class = ProductObjectProcessSerializer

    def get_queryset(self):
        product_object_id = self.kwargs.get('product_object_id')
        return ProductObjectProcess.objects.filter(product_object_id=product_object_id)

    def perform_create(self, serializer):
        product_object_id = self.kwargs.get('product_object_id')
        product_object = get_object_or_404(ProductObject, pk=product_object_id)
        serializer.save(product_object=product_object)


class ProductObjectProcessLogViewSet(viewsets.ModelViewSet):
    serializer_class = ProductObjectProcessLogSerializer

    def get_queryset(self):
        product_object_process_id = self.kwargs.get('product_object_process_id')
        return ProductObjectProcessLog.objects.filter(product_object_process_id=product_object_process_id)

    def perform_create(self, serializer):
        product_object_process_id = self.kwargs.get('product_object_process_id')
        pop = get_object_or_404(ProductObjectProcess, pk=product_object_process_id)
        serializer.save(product_object_process=pop)



class ProductMoveView(APIView):
    @transaction.atomic
    def post(self, request, process_id):
        serializer = ProductMoveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj = serializer.validated_data["product_object"]
        who_exit = serializer.validated_data["who_exit"]

        current_process = obj.current_process
        if not current_process or current_process.id != process_id:
            return Response(
                {"error": "Obiekt nie znajduje się w podanym procesie."},
                status=400
            )

        current_po_proc = obj.assigned_processes.filter(process=current_process).first()
        if not current_po_proc:
            return Response({"error": "Brak przypisanego procesu do obiektu."}, status=400)

        try:
            log = current_po_proc.logs.latest("entry_time")
        except ProductObjectProcessLog.DoesNotExist:
            return Response({"error": "Brak logu wejścia dla bieżącego procesu."}, status=400)

        log.exit_time = now()
        log.who_exit = who_exit
        log.save()

        if not current_process.can_multi:
            current_po_proc.is_completed = True
            current_po_proc.completed_at = now()
            current_po_proc.save()

        if current_process.changing_exp_date and current_process.how_much_days_exp_date:
            obj.exp_date_in_process = now().date() + timedelta(days=current_process.how_much_days_exp_date)

        obj.current_place = None
        obj.save()

        return Response({
            "status": "obiekt w drodze",
            "from_process": current_process.name,
        }, status=200)
        

class ProductReceiveView(APIView):
    @transaction.atomic
    def post(self, request, process_id):
        serializer = ProductReceiveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj = serializer.validated_data["product_object"]
        who_entry = serializer.validated_data["who_entry"]
        place_name = serializer.validated_data["place_name"]

        try:
            target_process = ProductProcess.objects.get(id=process_id)
        except ProductProcess.DoesNotExist:
            return Response({"error": "Proces nie istnieje."}, status=400)

        if target_process.product != obj.product:
            return Response({"error": "Proces nie należy do tego samego produktu."}, status=400)


        if obj.current_process and obj.current_process.id == process_id:
            return Response({"error": "Obiekt już znajduje się w tym procesie."}, status=400)

        previous_process = ProductProcess.objects.filter(
            product=obj.product,
            order=target_process.order - 1
        ).first()

        if previous_process:
            prev_proc_instance = obj.assigned_processes.filter(process=previous_process).first()
            if not prev_proc_instance or not prev_proc_instance.is_completed:
                return Response({"error": "Poprzedni proces nie został ukończony."}, status=400)

        place, _ = Place.objects.get(name=place_name)

        target_po_proc = obj.assigned_processes.filter(process=target_process).first()
        if not target_po_proc:
            return Response({"error": "Brak przypisania procesu do obiektu."}, status=400)

        if target_po_proc.logs.exists():
            return Response({"error": "Obiekt został już odebrany w tym procesie."}, status=400)

        obj.current_process = target_process
        obj.current_place = place
        obj.save()

        ProductObjectProcessLog.objects.create(
            product_object_process=target_po_proc,
            who_entry=who_entry,
            place=place
        )

        return Response({
            "status": "obiekt odebrany",
            "current_process": target_process.name,
            "place": place.name
        }, status=200)