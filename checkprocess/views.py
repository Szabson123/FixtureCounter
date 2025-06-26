from rest_framework import viewsets, status

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db import transaction, IntegrityError, models

from .models import Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place, AppToKill
from .serializers import ProductSerializer, ProductProcessSerializer, ProductObjectSerializer, ProductObjectProcessSerializer, ProductObjectProcessLogSerializer, PlaceSerializer, ProductMoveSerializer, ProductReceiveSerializer

from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from .filters import ProductObjectFilter
from .utils import parse_full_sn, check_fifo_violation

from datetime import timedelta
from django.utils.timezone import now, localtime


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
        queryset = ProductObject.objects.filter(product_id=product_id)

        return queryset.exclude(
            mother_object__isnull=False,
            mother_object__current_process=models.F('current_process')
        )
    
    @action(detail=True, methods=['get'], url_path='children')
    def get_children(self, request, pk=None, **kwargs):
        product_object = self.get_object()
        
        if not product_object.is_mother:
            return Response([], status=200)

        children = product_object.child_object.all()
        serializer = self.get_serializer(children, many=True)
        return Response(serializer.data, status=200)
    
    @action(detail=True, methods=['patch'], url_path='change-place')
    def change_place(self, request, pk=None, **kwargs):
        obj = self.get_object()
        new_place_name = request.data.get("place_name")

        if not new_place_name:
            return Response({"error": "Pole 'place_name' jest wymagane."}, status=400)

        if not obj.current_process:
            return Response({"error": "Obiekt nie znajduje się w żadnym procesie."}, status=400)

        try:
            new_place = Place.objects.get(name=new_place_name)
        except Place.DoesNotExist:
            return Response({"error": f"Miejsce '{new_place_name}' nie istnieje."}, status=400)

        if new_place.process != obj.current_process:
            return Response({
                "error": "Nowe miejsce nie należy do tego samego procesu, w którym znajduje się obiekt."
            }, status=400)

        obj.current_place = new_place
        obj.save(update_fields=["current_place"])

        return Response({
            "status": "Zmieniono miejsce obiektu.",
            "new_place": new_place.name
        }, status=200)


    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, pk=product_id)

        place_name = serializer.validated_data.pop('place_name', None)
        who_entry = serializer.validated_data.pop('who_entry', None)
        full_sn = serializer.validated_data.get('full_sn')
        
        mother_sn = serializer.validated_data.pop('mother_sn', None)
        mother_obj = None

        if not place_name or not who_entry or not full_sn:
            raise ValidationError("Brakuje 'place', 'who_entry' lub 'full_sn' w danych.")

        try:
            serial_number, production_date, expire_date, serial_type, q_code = parse_full_sn(full_sn)
        except ValueError as e:
            raise ValidationError(str(e))

        try:
            with transaction.atomic():
                place_obj, _ = Place.objects.get_or_create(name=place_name)

                if mother_sn:
                    try:
                        mother_serial, _, _, m_serial_type, m_q_code = parse_full_sn(mother_sn)
                        mother_obj = ProductObject.objects.get(serial_number=mother_serial)

                        if not mother_obj.is_mother:
                            raise ValidationError("Podany mother_sn nie należy do obiektu matki.")

                        child_limit = mother_obj.product.child_limit or 0
                        current_children = mother_obj.child_object.count()
                        if child_limit and current_children >= child_limit:
                            raise ValidationError(f"Obiekt matka osiągnął limit dzieci ({child_limit}).")

                        serializer.validated_data['mother_object'] = mother_obj

                    except ProductObject.DoesNotExist:
                        raise ValidationError("Obiekt matka o podanym numerze seryjnym nie istnieje.")
                    except ValueError as e:
                        raise ValidationError(f"Błąd w analizie mother_sn: {e}")

                serializer.validated_data['serial_number'] = serial_number
                serializer.validated_data['production_date'] = production_date
                serializer.validated_data['expire_date'] = expire_date
                serializer.validated_data['product'] = product

                if serial_type == "M" and q_code == "12":
                    serializer.validated_data['is_mother'] = True

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

        except IntegrityError as e:
            if "unique" in str(e).lower():
                raise ValidationError({"error": "Taki obiekt już istnieje"})
            raise ValidationError("Błąd podczas zapisu")


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

        full_sn = serializer.validated_data["full_sn"]
        who_exit = serializer.validated_data["who_exit"]

        try:
            obj = ProductObject.objects.get(full_sn=full_sn)
        except ProductObject.DoesNotExist:
            return Response({"error": "Obiekt o podanym numerze SN nie istnieje."}, status=400)
        
        if obj.end:
            return Response({
                "error": "Obiekt zakończył już swój cykl życia i nie może być modyfikowany.",
                "code": "object_ended"
            }, status=400)

        current_process = obj.current_process
        if not current_process or current_process.id != process_id:
            return Response({"error": "Obiekt nie znajduje się w podanym procesie."}, status=400)

        current_po_proc = obj.assigned_processes.filter(process=current_process).first()
        if not current_po_proc:
            return Response({"error": "Brak przypisanego procesu do obiektu."}, status=400)

        try:
            log = current_po_proc.logs.latest("entry_time")
        except ProductObjectProcessLog.DoesNotExist:
            return Response({"error": "Brak logu wejścia dla bieżącego procesu."}, status=400)

        if current_process.respect_quranteen_time and obj.quranteen_time and now() < obj.quranteen_time:
            return Response({
                "error": "Obiekt znajduje się na kwarantannie do: {}".format(
                    localtime(obj.quranteen_time).strftime("%Y-%m-%d %H:%M")
                )
            }, status=400)

        if obj.is_mother and current_process.expecting_child:
            has_children = obj.child_object.filter(current_process=current_process).exists()
            if not has_children:
                return Response({
                    "status": "karton nie został przeniesiony",
                    "show_add_child_modal": True,
                    "message": "Dodaj dzieci do kartonu zanim go przeniesiesz.",
                    "serial_number": obj.serial_number
                }, status=200)
                
        # FIFO violation check
        violation = check_fifo_violation(obj)
        if violation:
            return Response(violation, status=400)        

        log.exit_time = now()
        log.who_exit = who_exit
        log.save()

        if not current_process.can_multi:
            current_po_proc.is_completed = True
            current_po_proc.completed_at = now()
            current_po_proc.save()

        if current_process.changing_exp_date and current_process.how_much_days_exp_date:
            obj.exp_date_in_process = now().date() + timedelta(days=current_process.how_much_days_exp_date)

        if current_process.quranteen_time:
            obj.quranteen_time = now() + timedelta(hours=current_process.quranteen_time)

        obj.current_place = None
        obj.save()

        if not obj.is_mother and obj.mother_object is not None:
            mother = obj.mother_object
            obj.ex_mother = mother.serial_number
            obj.mother_object = None
            obj.save(update_fields=["mother_object", "ex_mother"])

            if not mother.child_object.exists():
                mother.delete()

        children_moved = 0
        if obj.is_mother:
            children = obj.child_object.filter(current_process=current_process)
            for child in children:
                child_po_proc = child.assigned_processes.filter(process=current_process).first()
                if not child_po_proc:
                    continue
                try:
                    child_log = child_po_proc.logs.latest("entry_time")
                except ProductObjectProcessLog.DoesNotExist:
                    continue

                child_log.exit_time = now()
                child_log.who_exit = who_exit
                child_log.save()

                if not current_process.can_multi:
                    child_po_proc.is_completed = True
                    child_po_proc.completed_at = now()
                    child_po_proc.save()

                if current_process.changing_exp_date and current_process.how_much_days_exp_date:
                    child.exp_date_in_process = now().date() + timedelta(days=current_process.how_much_days_exp_date)

                if current_process.quranteen_time:
                    child.quranteen_time = now() + timedelta(hours=current_process.quranteen_time)

                child.current_place = None
                child.save()
                children_moved += 1
                
            if not obj.child_object.exists():
                obj.delete()

        return Response({
            "status": "obiekt w drodze",
            "from_process": current_process.name,
            "children_moved": children_moved
        }, status=200)
        
        
class ProductReceiveView(APIView):
    @transaction.atomic
    def post(self, request, process_id):
        serializer = ProductReceiveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        full_sn = serializer.validated_data["full_sn"]
        who_entry = serializer.validated_data["who_entry"]
        place_name = serializer.validated_data["place_name"]
        
        place, _ = Place.objects.get_or_create(name=place_name)
        
        if place.only_one_product_object:
            if ProductObject.objects.filter(current_place=place).exists():
                return Response({
                    "error": f"W miejscu '{place.name}' znajduje się już inny obiekt. Nie można przyjąć więcej niż jednego.",
                    "code": "place_occupied"
                }, status=400)

        def set_kill_flag(value=True):
            AppToKill.objects.filter(line_name__name=place_name).update(killing_flag=value)

        set_kill_flag(True)
        
        try:
            obj = ProductObject.objects.get(full_sn=full_sn)
        except ProductObject.DoesNotExist:
            return Response({"error": "Obiekt o podanym numerze SN nie istnieje."}, status=400)

        if obj.end:
            return Response({
                "error": "Obiekt zakończył już swój cykl życia i nie może być modyfikowany.",
                "code": "object_ended"
            }, status=400)

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

        # Jeśli proces końcowy – ustaw end=True i zakończ poprzedni proces
        if target_process.ending_process:
            obj.end = True
            obj.save(update_fields=["end"])

            if previous_process:
                prev_proc_instance = obj.assigned_processes.filter(process=previous_process).first()
                if prev_proc_instance and not prev_proc_instance.is_completed:
                    prev_proc_instance.is_completed = True
                    prev_proc_instance.completed_at = now()
                    prev_proc_instance.save()

        # Walidacja poprzedniego procesu (o ile to NIE jest proces końcowy)
        if previous_process and not target_process.ending_process:
            prev_proc_instance = obj.assigned_processes.filter(process=previous_process).first()
            if not prev_proc_instance or not prev_proc_instance.is_completed:
                return Response({"error": "Poprzedni proces nie został ukończony."}, status=400)

        target_po_proc = obj.assigned_processes.filter(process=target_process).first()
        if not target_po_proc:
            return Response({"error": "Brak przypisania procesu do obiektu."}, status=400)

        if target_po_proc.logs.exists():
            return Response({"error": "Obiekt został już odebrany w tym procesie."}, status=400)

        # Sukces – wyłącz flagę kill
        set_kill_flag(False)
        
        if place.only_one_product_object:
            exists = ProductObject.objects.filter(current_place=place).exclude(id=obj.id).exists()
            if exists:
                return Response({
                    "error": f"W miejscu '{place.name}' znajduje się już inny obiekt. Nie można przyjąć więcej niż jednego.",
                    "code": "place_occupied"
                }, status=400)

        obj.current_process = target_process
        obj.current_place = place
        obj.save()

        if not obj.is_mother and obj.mother_object is not None:
            obj.ex_mother = obj.mother_object.serial_number
            obj.mother_object = None
            obj.save(update_fields=["mother_object", "ex_mother"])

        ProductObjectProcessLog.objects.create(
            product_object_process=target_po_proc,
            who_entry=who_entry,
            place=place
        )

        children_received = 0
        if obj.is_mother and previous_process:
            children = obj.child_object.filter(current_process=previous_process)
            for child in children:
                child_po_proc = child.assigned_processes.filter(process=target_process).first()
                if not child_po_proc or child_po_proc.logs.exists():
                    continue

                child.current_process = target_process
                child.current_place = place
                child.save()

                ProductObjectProcessLog.objects.create(
                    product_object_process=child_po_proc,
                    who_entry=who_entry,
                    place=place
                )
                children_received += 1

        return Response({
            "status": "obiekt odebrany",
            "current_process": target_process.name,
            "place": place.name,
            "children_received": children_received
        }, status=200)


class AppKillStatusView(APIView):
    def get(self, request):
        line_name = request.query_params.get("line")

        if not line_name:
            return Response({"error": "Brakuje parametru 'line'"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            place = Place.objects.get(name=line_name)
            app_kill = AppToKill.objects.get(line_name=place)
            return Response({"kill": app_kill.killing_flag}, status=200)

        except Place.DoesNotExist:
            return Response({"error": f"Linia '{line_name}' nie istnieje."}, status=404)
        except AppToKill.DoesNotExist:
            return Response({"kill": False}, status=200)
        
        
class QuickAddToMotherView(APIView):
    @transaction.atomic
    def post(self, request):
        full_sn = request.data.get("full_sn")
        mother_sn = request.data.get("mother_sn")
        who_entry = request.data.get("who_entry")

        if not all([full_sn, mother_sn, who_entry]):
            return Response({"error": "Brakuje pełnych danych."}, status=400)

        try:
            sn, prod_date, exp_date, serial_type, q_code = parse_full_sn(full_sn)
            mother_sn_parsed, *_ = parse_full_sn(mother_sn)
        except Exception as e:
            return Response({"error": f"Błąd SN: {e}"}, status=400)

        try:
            mother = ProductObject.objects.get(serial_number=mother_sn_parsed)
        except ProductObject.DoesNotExist:
            return Response({"error": "Nie znaleziono matki."}, status=404)

        if not mother.is_mother:
            return Response({"error": "Obiekt matka nie jest kartonem."}, status=400)
        
        child_limit = mother.product.child_limit or 0
        current_children = mother.child_object.count()
        if child_limit and current_children >= child_limit:
            return Response(
                {"error": f"Obiekt matka osiągnął limit dzieci ({child_limit})."},
                status=400
            )

        if ProductObject.objects.filter(serial_number=sn).exists():
            return Response({"error": "Obiekt już istnieje."}, status=400)

        obj = ProductObject.objects.create(
            product=mother.product,
            serial_number=sn,
            full_sn=full_sn,
            production_date=prod_date,
            expire_date=exp_date,
            mother_object=mother,
            current_process=mother.current_process,
            current_place=mother.current_place
        )

        processes = mother.product.processes.order_by('order')
        for process in processes:
            pop = ProductObjectProcess.objects.create(
                product_object=obj,
                process=process,
                is_completed=False
            )
            if process == mother.current_process:
                ProductObjectProcessLog.objects.create(
                    product_object_process=pop,
                    who_entry=who_entry,
                    place=mother.current_place
                )

        return Response({"status": "Dodano obiekt do kartonu", "child_sn": sn}, status=201)