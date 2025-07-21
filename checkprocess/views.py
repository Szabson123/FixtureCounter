
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError, models
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.timezone import now, localtime

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from .filters import ProductObjectFilter
from .parsers import get_parser
from .utils import check_fifo_violation, detect_parser_type
from .validation import ValidationErrorWithCode, ProcessEntryValidator
from .models import Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place, AppToKill, Edge, SubProduct
from .serializers import(ProductSerializer, ProductProcessSerializer, ProductObjectSerializer, ProductObjectProcessSerializer,
                        ProductObjectProcessLogSerializer, PlaceSerializer, ProductMoveSerializer, ProductReceiveSerializer,
                        EdgeSerializer)

from datetime import timedelta, date
from rest_framework.pagination import PageNumberPagination


class BasicProcessPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100
    

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
    pagination_class = BasicProcessPagination

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
    
    @action(detail=False, methods=["patch"], url_path="change-place-by-sn")
    def change_place_by_sn(self, request, **kwargs):
        full_sn = request.data.get("obj_full_sn")
        new_place_name = request.data.get("place_name")

        if not full_sn:
            return Response({"error": "Pole 'obj_full_sn' jest wymagane."}, status=400)
        if not new_place_name:
            return Response({"error": "Pole 'place_name' jest wymagane."}, status=400)

        try:
            obj = ProductObject.objects.get(full_sn=full_sn)
        except ProductObject.DoesNotExist:
            return Response({"error": f"Obiekt SN '{full_sn}' nie istnieje."}, status=404)

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
            "new_place": new_place.name,
            "object_id": obj.id,
            "serial_number": obj.serial_number
        }, status=200)


    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, pk=product_id)

        place_name = serializer.validated_data.pop('place_name', None)
        who_entry = serializer.validated_data.pop('who_entry', None)
        full_sn = serializer.validated_data.get('full_sn')
        
        mother_sn = serializer.validated_data.pop('mother_sn', None)
        mother_obj = None
        
        parser_type = detect_parser_type(full_sn)

        if not place_name or not who_entry or not full_sn:
            raise ValidationError("Brakuje 'place', 'who_entry' lub 'full_sn' w danych.")

        try:
            parser = get_parser(parser_type)
            sub_product, serial_number, production_date, expire_date, serial_type, q_code = parser.parse(full_sn)
        except ValueError as e:
            raise ValidationError(str(e))
        
        try:
            sub_product_obj = SubProduct.objects.get(product=product, name=sub_product)
        except SubProduct.DoesNotExist:
            raise ValidationError(f"SubProduct '{sub_product}' nie istnieje dla produktu '{product.name}'.")

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
                serializer.validated_data['sub_product'] = sub_product_obj
    
                if serial_type and serial_type == "M" and q_code == "12":
                    serializer.validated_data['is_mother'] = True

                product_object = serializer.save()

                product_object.current_place = place_obj
                product_object.save()

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
        
        try:
            validator = ProcessEntryValidator(full_sn, process_id, place_name)
            obj, process, target_po_proc = validator.run()
            previous_process = validator.previous_process
        except ValidationErrorWithCode as e:
            return Response({"error": e.message, "code": e.code}, status=400)

        obj.current_process = process
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
                child_po_proc = child.assigned_processes.filter(process=process).first()
                if not child_po_proc or child_po_proc.logs.exists():
                    continue

                child.current_process = process
                child.current_place = place
                child.save()

                ProductObjectProcessLog.objects.create(
                    product_object_process=child_po_proc,
                    who_entry=who_entry,
                    place=place
                )
                children_received += 1
        
        AppToKill.objects.filter(line_name__name=place.name).update(killing_flag=False)

        return Response({
            "status": "obiekt odebrany",
            "current_process": process.name,
            "place": place.name,
            "children_received": children_received
        }, status=200)


class AppKillStatusView(APIView):
    def get(self, request):
        line_name = request.query_params.get("line")

        if not line_name:
            return Response({"error": "Brakuje parametru 'line'"}, status=status.HTTP_400_BAD_REQUEST)

        def set_kill_flag(value=True):
            AppToKill.objects.filter(line_name__name=line_name).update(killing_flag=value)

        try:
            place = Place.objects.get(name=line_name)

            expired_products = ProductObject.objects.filter(
                current_place=place,
                exp_date_in_process__lt=date.today()
            )

            if expired_products.exists():
                set_kill_flag(True)
                return Response({
                    "kill": True,
                    "expired": True,
                    "message": "Wykryto przeterminowany produkt na linii."
                }, status=200)

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
            )
            if process == mother.current_process:
                ProductObjectProcessLog.objects.create(
                    product_object_process=pop,
                    who_entry=who_entry,
                    place=mother.current_place
                )

        return Response({"status": "Dodano obiekt do kartonu", "child_sn": sn}, status=201)
    

class GraphImportView(APIView):
    @transaction.atomic
    def post(self, request, product_id):
        product = Product.objects.get(id=product_id)

        nodes_data = request.data.get('nodes', [])
        edges_data = request.data.get('edges', [])

        node_serializer = ProductProcessSerializer(data=nodes_data, many=True, context={'product': product})
        node_serializer.is_valid(raise_exception=True)

        created_nodes = []
        for item in node_serializer.validated_data:
            node = ProductProcess.objects.create(**item)
            created_nodes.append(node)

        edge_serializer = EdgeSerializer(data=edges_data, many=True)
        edge_serializer.is_valid(raise_exception=True)

        node_map = {str(n.id): n for n in created_nodes}

        for n in ProductProcess.objects.filter(product=product):
            node_map[str(n.id)] = n

        for item in edge_serializer.validated_data:
            source = node_map.get(str(item['source']))
            target = node_map.get(str(item['target']))
            if source and target:
                Edge.objects.create(
                    id=item['id'],
                    type=item['type'],
                    animated=item['animated'],
                    label=item.get('label', ''),
                    source=source,
                    target=target,
                    source_handle=item.get('source_handle'),
                    target_handle=item.get('target_handle')
                )

        return Response({'status': 'imported'}, status=status.HTTP_201_CREATED)
    
    def get(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)

        nodes = ProductProcess.objects.filter(product=product)
        edges = Edge.objects.filter(
            source__product=product,
            target__product=product
        )

        node_serializer = ProductProcessSerializer(nodes, many=True)
        edge_serializer = EdgeSerializer(edges, many=True)

        return Response({
            'name': product.name,
            'nodes': node_serializer.data,
            'edges': edge_serializer.data
        })
        