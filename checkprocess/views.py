
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError, models
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from .filters import ProductObjectFilter, ProductObjectProcessLogFilter
from .parsers import get_parser
from .utils import check_fifo_violation, detect_parser_type, get_printer_info_from_card
from .validation import ProcessMovementValidator, ValidationErrorWithCode
from .models import Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place, AppToKill, Edge, SubProduct, LastProductOnPlace, PlaceGroupToAppKill
from .serializers import(ProductSerializer, ProductProcessSerializer, ProductObjectSerializer, ProductObjectProcessSerializer,
                        ProductObjectProcessLogSerializer, PlaceSerializer, EdgeSerializer, BulkProductObjectCreateSerializer, BulkProductObjectCreateToMotherSerializer)

from checkprocess.services.movement_service import MovementHandler

from datetime import timedelta, date, datetime
from rest_framework.pagination import PageNumberPagination


class BasicProcessPagination(PageNumberPagination):
    page_size = 25
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
        process_uuid = self.kwargs.get('process_uuid')

        return ProductObject.objects.filter(
            product_id=product_id,
            current_process_id=process_uuid
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
        process_uuid = self.kwargs.get('process_uuid')
        
        product = get_object_or_404(Product, pk=product_id)
        process = get_object_or_404(ProductProcess, pk=process_uuid)

        place_name = serializer.validated_data.pop('place_name', None)
        who_entry = serializer.validated_data.pop('who_entry', None)
        full_sn = serializer.validated_data.get('full_sn')
        
        mother_sn = serializer.validated_data.pop('mother_sn', None)
        mother_obj = None
        
        parser_type = detect_parser_type(full_sn)
        
        if not process.starts:
            raise ValidationError("To nie jest process startowy")

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
                try:
                    place_obj = Place.objects.get(name=place_name, process=process)
                except Place.DoesNotExist:
                    raise ValidationError(
                        {"message": f"Takie miejsce nie istnieje: {place_name}", "code": "place_not_found"}
                    )
    
                serializer.validated_data['serial_number'] = serial_number
                serializer.validated_data['production_date'] = production_date
                serializer.validated_data['expire_date'] = expire_date
                serializer.validated_data['product'] = product
                serializer.validated_data['sub_product'] = sub_product_obj
    
                if serial_type and serial_type == "M" and q_code == "12":
                    serializer.validated_data['is_mother'] = True

                product_object = serializer.save()

                product_object.current_place = place_obj
                product_object.current_process = process
                
                product_object.save()
                
                ProductObjectProcessLog.objects.create(product_object=product_object, process=process, entry_time=timezone.now(), who_entry=who_entry, place=place_obj)

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
    queryset = ProductObjectProcessLog.objects.all()

    search_fields = ['product_object__serial_number', 'product_object__full_sn']
    ordering_fields = ['entry_time', 'exit_time']
    ordering = ['-entry_time']

    def get_queryset(self):
        queryset = super().get_queryset()
        sn = self.request.query_params.get('sn')

        if sn:
            try:
                product_object = ProductObject.objects.get(
                    models.Q(serial_number=sn) | models.Q(full_sn=sn)
                )
            except ProductObject.DoesNotExist:
                raise ValidationError({"sn": "Product object with this SN not found."})

            queryset = queryset.filter(product_object=product_object)
            
        else:
            raise ValidationError({"sn": "Musisz podać jaki kolwiek sn"})

        return queryset

        
class ProductMoveView(APIView):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        
        process_uuid = self.kwargs.get('process_uuid')
        full_sn = request.data.get('full_sn')
        place_name = request.data.get('place_name')
        movement_type = request.data.get('movement_type')
        who = request.data.get('who')
        result = request.data.get('result')

        try:
            validator = ProcessMovementValidator(process_uuid, full_sn, place_name, movement_type, who)
            validator.run()
            
            product_object = validator.product_object
            place = validator.place
            process = validator.process
            
            handler = MovementHandler.get_handler(movement_type, product_object, place, process, who, result)
            handler.execute()
            
            return Response(
                {"detail": "Ruch został wykonany pomyślnie."},
                status=status.HTTP_200_OK
            )
        
        except ValidationErrorWithCode as e:
            return Response(
                {"detail": e.message, "code": e.code},
                status=status.HTTP_400_BAD_REQUEST
            )
            

class ScrapProduct(APIView):
    def post(self, request, *args, **kwargs):
        process_uuid = self.kwargs.get('process_uuid')
        place_name = request.data.get('place_name')
        who = request.data.get('who')
        full_sn = request.data.get("full_sn")
        movement_type = request.data.get("movement_type")
        
        # For logic its always receive but we are using class ProcessMovementValidator and class requires it.
        if movement_type != 'trash':
            raise ValidationError("Tylko przyjmowanie dla tego enpointu")
        
        try:
            validator = ProcessMovementValidator(process_uuid, full_sn, place_name, movement_type, who)
            validator.run()
            
            product_object = validator.product_object
            place = validator.place
            process = validator.process
            
            ProductObjectProcessLog.objects.create(product_object=product_object, process=process, who_entry=who, place=place)
            
            product_object.end = True
            product_object.current_process = process
            product_object.current_place = place
            product_object.save()
            
            return Response(
                {"detail": "Ruch został wykonany pomyślnie."},
                status=status.HTTP_200_OK
            )
        
        except ValidationErrorWithCode as e:
            return Response(
                {"detail": e.message, "code": e.code},
                status=status.HTTP_400_BAD_REQUEST
            )
    

class ContinueProduction(APIView):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        process_uuid = self.kwargs.get('process_uuid')
        place_name = request.data.get('place_name')
        movement_type = request.data.get('movement_type')
        who = request.data.get('who')
        full_sn = request.data.get('full_sn')
        
        # For logic its always receive but we are using class ProcessMovementValidator and class requires it.
        if movement_type != 'receive':
            raise ValidationError("Tylko przyjmowanie dla tego enpointu")
        
        try:
            validator = ProcessMovementValidator(process_uuid, full_sn, place_name, movement_type, who)
            validator.run()
            
            product_object = validator.product_object
            place = validator.place
            process = validator.process
            
            last_production = (
                LastProductOnPlace.objects
                .filter(product_process=process, place=place)
                .order_by('-date')
                .first()
            )

            if not last_production:
                raise ValidationError("Brak historii pasty na tym stanowisku – nie można kontynuować produkcji.")

            if last_production.p_type.name != product_object.sub_product.name:
                raise ValidationError("Nie możesz użyć tej pasty do tego produktu – ostatnia używana była inna.")

            
            handler = MovementHandler.get_handler(movement_type, product_object, place, process, who)
            handler.execute()
            
            return Response(
                {"detail": "Ruch został wykonany pomyślnie."},
                status=status.HTTP_200_OK
            )
        
        except ValidationErrorWithCode as e:
            return Response(
                {"detail": e.message, "code": e.code},
                status=status.HTTP_400_BAD_REQUEST
            )
            

class ProductStartNewProduction(APIView):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        
        process_uuid = self.kwargs.get('process_uuid')
        production_card = request.data.get('production_card')
        place_name = request.data.get('place_name')
        movement_type = request.data.get('movement_type')
        who = request.data.get('who')
        full_sn = request.data.get('full_sn')
        
        # For logic its always receive but we are using class ProcessMovementValidator and class requires it.
        if movement_type != 'receive':
            raise ValidationError("Tylko przyjmowanie dla tego enpointu")
        
        if not production_card:
            raise ValidationError("Bez karty nie możemy pójść dalej")
        
        try:
            validator = ProcessMovementValidator(process_uuid, full_sn, place_name, movement_type, who)
            validator.run()
            
            product_object = validator.product_object
            
            place = validator.place
            process = validator.process
            
            if not hasattr(process, 'defaults') or not process.defaults.production_process_type:
                raise ValidationError("Ten proces nie pozwala na rozpoczęcie produkcji przez ten endpoint.")
            
            normalized_name = get_printer_info_from_card(production_card)
            
            if not product_object.sub_product:
                raise ValidationError("Obiekt nie ma przypisanego subproduktu.")


            if product_object.sub_product.name != normalized_name:
                raise ValidationError(f"Nie możesz użyc tego typu pasty dla tego produktu")
            
            handler = MovementHandler.get_handler(movement_type, product_object, place, process, who)
            handler.execute()
            
            LastProductOnPlace.objects.create(product_process=process, place=place, p_type=product_object.sub_product)
            
            return Response(
                {"detail": "Ruch został wykonany pomyślnie."},
                status=status.HTTP_200_OK
            )
        
        except ValidationErrorWithCode as e:
            return Response(
                {"detail": e.message, "code": e.code},
                status=status.HTTP_400_BAD_REQUEST
            )
            
                
class AppKillStatusView(APIView):
    def get(self, request):
        group_name = request.query_params.get("group")
        if not group_name:
            return Response({"error": "Brakuje parametru 'group'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            group = PlaceGroupToAppKill.objects.get(name=group_name)
        except PlaceGroupToAppKill.DoesNotExist:
            return Response({"error": f"Grupa '{group_name}' nie istnieje."}, status=status.HTTP_404_NOT_FOUND)

        places_qs = (
            Place.objects
            .filter(group=group, process__killing_app=True)
            .only("id", "name")
        )

        place_ids = list(places_qs.values_list("id", flat=True))

        if not place_ids:
            return Response({
                "group": group_name,
                "expired": False,
                "places_with_expired": [],
                "kill": False,
                "per_place": {}
            }, status=200)

        expired_ids = list(
            ProductObject.objects.filter(
                current_place_id__in=place_ids,
                exp_date_in_process__lt=date.today()
            ).values_list("current_place_id", flat=True).distinct()
        )
        places_with_expired = list(
            Place.objects.filter(id__in=expired_ids).values_list("name", flat=True)
        )
        expired_any = bool(expired_ids)

        per_place_flags = dict(
            AppToKill.objects.filter(line_name_id__in=place_ids)
            .values_list("line_name__name", "killing_flag")
        )
        kill_any = any(per_place_flags.values()) if per_place_flags else False

        return Response({
            "group": group_name,
            "expired": expired_any,
            "places_with_expired": places_with_expired,
            "kill": kill_any,
            "per_place": per_place_flags
        }, status=200)
        
        
class QuickAddToMotherView(APIView):
    @transaction.atomic
    def post(self, request):
        full_sn = request.data.get("full_sn")
        mother_sn = request.data.get("mother_sn")
        who_entry = request.data.get("who_entry")

        if not all([full_sn, mother_sn, who_entry]):
            return Response({"error": "Brakuje pełnych danych."}, status=400)
        
        parser_type = detect_parser_type(full_sn)
        parser = get_parser(parser_type)

        try:
            sn, prod_date, exp_date, serial_type, q_code = parser.parse(full_sn)
            mother_sn_parsed, *_ = parser.parse(mother_sn)
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
        
        
class BulkProductObjectCreateView(APIView):
    def post(self, request, product_id, process_uuid):
        serializer = BulkProductObjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        place_name = serializer.validated_data['place']
        who_entry = serializer.validated_data['who_entry']
        objects_data = serializer.validated_data['objects']

        product = get_object_or_404(Product, pk=product_id)
        process = get_object_or_404(ProductProcess, pk=process_uuid)

        if not process.starts:
            raise ValidationError("To nie jest process startowy")

        try:
            with transaction.atomic():
                try:
                    place_obj = Place.objects.get(name=place_name, process=process)
                except:
                    raise ValidationError("Takie miejsce nie istnieje")
                created_serials = []

                for obj in objects_data:
                    full_sn = obj.get('full_sn')
                    if not full_sn:
                        raise ValidationError("Brakuje 'full_sn' w jednym z obiektów.")

                    parser_type = detect_parser_type(full_sn)
                    try:
                        parser = get_parser(parser_type)
                        sub_product, serial_number, production_date, expire_date, serial_type, q_code = parser.parse(full_sn)
                    except ValueError as e:
                        raise ValidationError(f"Błąd parsowania SN '{full_sn}': {str(e)}")

                    try:
                        sub_product_obj = SubProduct.objects.get(product=product, name=sub_product)
                    except SubProduct.DoesNotExist:
                        raise ValidationError(f"SubProduct '{sub_product}' nie istnieje dla produktu '{product.name}'.")

                    product_object = ProductObject(
                        full_sn=full_sn,
                        product=product,
                        sub_product=sub_product_obj,
                        serial_number=serial_number,
                        production_date=production_date,
                        expire_date=expire_date,
                        current_place=place_obj,
                        current_process=process
                    )

                    if serial_type and serial_type == "M" and q_code == "12":
                        product_object.is_mother = True

                    product_object.save()
                    created_serials.append(serial_number)

                    ProductObjectProcessLog.objects.create(
                        product_object=product_object,
                        process=process,
                        entry_time=timezone.now(),
                        who_entry=who_entry,
                        place=place_obj
                    )

        except IntegrityError as e:
            if "unique" in str(e).lower():
                raise ValidationError({"error": "Jeden z obiektów już istnieje"})
            raise ValidationError("Błąd podczas zapisu")

        return Response({"message": "Dodano obiekty", "serials": created_serials}, status=status.HTTP_201_CREATED)

            
class BulkProductObjectCreateAndAddMotherView(APIView):
    def post(self, request, product_id, process_uuid):
        serializer = BulkProductObjectCreateToMotherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        who_entry = serializer.validated_data['who_entry']
        objects_data = serializer.validated_data['objects']
        mother_sn = serializer.validated_data['mother_sn']

        product = get_object_or_404(Product, pk=product_id)
        process = get_object_or_404(ProductProcess, pk=process_uuid)

        mother = get_object_or_404(ProductObject, full_sn=mother_sn, is_mother=True)

        place_name = mother.current_place.name
        print(place_name)

        if not process.starts:
            raise ValidationError("To nie jest process startowy")

        try:
            with transaction.atomic():
                try:
                    place_obj = Place.objects.get(name=place_name, process=process)
                except Place.DoesNotExist:
                    raise ValidationError("Takie miejsce nie istnieje")
                created_serials = []

                for obj in objects_data:
                    full_sn = obj.get('full_sn')
                    if not full_sn:
                        raise ValidationError("Brakuje 'full_sn' w jednym z obiektów.")

                    parser_type = detect_parser_type(full_sn)
                    try:
                        parser = get_parser(parser_type)
                        sub_product, serial_number, production_date, expire_date, serial_type, q_code = parser.parse(full_sn)
                    except ValueError as e:
                        raise ValidationError(f"Błąd parsowania SN '{full_sn}': {str(e)}")

                    try:
                        sub_product_obj = SubProduct.objects.get(product=product, name=sub_product)
                    except SubProduct.DoesNotExist:
                        raise ValidationError(f"SubProduct '{sub_product}' nie istnieje dla produktu '{product.name}'.")

                    product_object = ProductObject(
                        full_sn=full_sn,
                        product=product,
                        sub_product=sub_product_obj,
                        serial_number=serial_number,
                        production_date=production_date,
                        expire_date=expire_date,
                        current_place=place_obj,
                        current_process=process,

                        mother_object = mother
                    )

                    product_object.save()
                    created_serials.append(serial_number)

                    ProductObjectProcessLog.objects.create(
                        product_object=product_object,
                        process=process,
                        entry_time=timezone.now(),
                        who_entry=who_entry,
                        place=place_obj
                    )

        except IntegrityError as e:
            if "unique" in str(e).lower():
                raise ValidationError({"error": "Jeden z obiektów już istnieje"})
            raise ValidationError("Błąd podczas zapisu")

        return Response({"message": "Dodano obiekty", "serials": created_serials}, status=status.HTTP_201_CREATED)