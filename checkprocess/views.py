
import requests

from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError, models
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import connection
from django.db.models import F, Count, Q
from django.db.models.functions import Coalesce

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, GenericAPIView
from rest_framework.filters import OrderingFilter

from .filters import ProductObjectFilter, ProductObjectProcessLogFilter
from .parsers import get_parser
from .utils import detect_parser_type, get_printer_info_from_card, poke_process
from .validation import ProcessMovementValidator, ValidationErrorWithCode
from .models import (Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place, AppToKill, Edge, SubProduct,
                    LastProductOnPlace, PlaceGroupToAppKill, MessageToApp)
from .serializers import(ProductSerializer, ProductProcessSerializer, ProductObjectSerializer, ProductObjectProcessSerializer,
                        ProductObjectProcessLogSerializer, PlaceSerializer, EdgeSerializer, BulkProductObjectCreateSerializer, BulkProductObjectCreateToMotherSerializer,
                        PlaceGroupToAppKillSerializer, RetoolingSerializer, StencilStartProdSerializer)

from checkprocess.services.movement_service import MovementHandler
from checkprocess.services.edge_service import EdgeSameInSameOut

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
    queryset = ProductObject.objects.all()

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductObjectFilter

    ordering_fields = [
        'serial_number',
        'created_at',
        'quranteen_time',
        'production_date',
        'exp_date_in_process',
        'expire_date',
        'expire_date_final',
        'sub_product__name',
        'current_place',
    ]

    ordering = ['-created_at']
    pagination_class = BasicProcessPagination

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        process_uuid = self.kwargs.get('process_uuid')

        return (
            ProductObject.objects.filter(
                Q(is_mother=True) | Q(mother_object__isnull=True),
                product_id=product_id,
                current_process_id=process_uuid
            )
            .annotate(
                expire_date_final=Coalesce(
                    F("exp_date_in_process"),
                    F("expire_date"),
                )
            )
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
                
                if serial_type == 'karton':
                    serializer.validated_data['is_mother'] = True
                
                product_object = serializer.save()

                product_object.current_place = place_obj
                product_object.current_process = process
                
                product_object.save()
                
                ProductObjectProcessLog.objects.create(product_object=product_object, process=process, entry_time=timezone.now(), who_entry=who_entry, place=place_obj)

        except IntegrityError as e:
            if "unique" in str(e).lower():
                raise ValidationError({"error": "Taki obiekt już istnieje"})
            raise ValidationError(f"Błąd podczas zapisu {e}")


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
    
    @action(detail=False, methods=['get'], url_path='all-logs')
    def all_logs(self, request):
        logs = (
            ProductObjectProcessLog.objects
            .select_related('product_object', 'process', 'place')
            .order_by('-entry_time')
        )

        serializer = self.get_serializer(logs, many=True)
        data = serializer.data

        return Response(data)


class ProductMoveView(APIView):
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
            new_place = product_object.current_place
            MessageToApp.objects.filter(line=new_place, send=False).update(send=True)
            handler = MovementHandler.get_handler(movement_type, product_object, place, process, who, result)
            handler.execute()

            obj = ProductObject.objects.get(full_sn=full_sn)
            
            return Response(
                {"detail": "Ruch został wykonany pomyślnie.",
                 "id": obj.id,
                 "is_mother": obj.is_mother},
                status=status.HTTP_200_OK
            )
        
        except ValidationErrorWithCode as e:
            return Response(
                {"detail": e.message, "code": e.code},
                status=status.HTTP_400_BAD_REQUEST
            )

        
class ProductMoveListView(APIView):
    def post(self, request, *args, **kwargs):
        
        process_uuid = self.kwargs.get('process_uuid')
        full_sn = request.data.get('full_sn')
        place_name = request.data.get('place_name')
        movement_type = request.data.get('movement_type')
        who = request.data.get('who')
        result = request.data.get('result')

        if not isinstance(full_sn, list):
            full_sn = [full_sn]
        
        product_objects = ProductObject.objects.filter(full_sn__in=full_sn)
        processes = product_objects.values_list("current_process_id", flat=True).distinct()
        if processes.count() > 1:
            return Response(
                {"detail": "Wszystkie obiekty muszą należeć do tego samego procesu."},
                status=status.HTTP_400_BAD_REQUEST
            )

        responses = []

        try:
            for sn in full_sn:
                validator = ProcessMovementValidator(process_uuid, sn, place_name, movement_type, who)
                validator.run()
                
                product_object = validator.product_object
                place = validator.place
                process = validator.process
                
                handler = MovementHandler.get_handler(movement_type, product_object, place, process, who, result)
                handler.execute()

                obj = ProductObject.objects.get(full_sn=sn)
                
                responses.append({
                    "id": obj.id,
                    "is_mother": obj.is_mother,
                    "full_sn": sn,
                    "detail": "Ruch został wykonany pomyślnie."
                })

                last_sn = sn 
            
            # To check if all in - in
            if movement_type == 'recive':
                edge_sets = EdgeSameInSameOut(process_uuid, last_sn)
                info = edge_sets.execute()
                responses.append(info)

            return Response(responses, status=status.HTTP_200_OK)

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
                raise ValidationErrorWithCode("Brak historii pasty na tym stanowsku", code="NO_PASTE_HISTORY")

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


class StencilStartNewProd(GenericAPIView):
    serializer_class = StencilStartProdSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        process_uuid = self.kwargs.get('process_uuid')

        place_name = data['place_name']
        movement_type = data['movement_type']
        who = data['who']
        full_sn = data['full_sn']

        try:
            validator = ProcessMovementValidator(process_uuid, full_sn, place_name, movement_type, who)
            validator.run()
            product_object = validator.product_object
            place = validator.place
            process = validator.process

            defaults = getattr(process, "defaults", None)
            if not defaults or not defaults.stencil_production_process_type:
                raise ValidationError({"error": "Ten proces nie pozwala na rozpoczęcie produkcji przez ten endpoint."})
            if not defaults.use_poke:
                raise ValidationError({"error": "Ten proces wymaga poke do aplikacji."})
            if defaults.use_poke:
                poke_process(7)
            
            handler = MovementHandler.get_handler(movement_type, product_object, place, process, who)
            handler.execute()
            
            message_one = 'Produkcja tym sitem trwa ponad 7.5 godziny za 30 min aplikacja zostanie wyłączona'
            message_two = 'Produkcja trwa już 8 godzin wyłączam aplikacje do czasu przezbrojenia'

            MessageToApp.objects.create(
                line=place,
                message=message_one,
                send = False,
                when_trigger = timezone.now() + timedelta(hours=7, minutes=30),
                product = product_object.product
            )

            MessageToApp.objects.create(
                line=place,
                message=message_two,
                send = False,
                when_trigger = timezone.now() + timedelta(hours=8),
                product = product_object.product
            )

            LastProductOnPlace.objects.create(product_process=process, place=place, )
            
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
    def post(self, request, *args, **kwargs):
        
        process_uuid = self.kwargs.get('process_uuid')
        production_card = request.data.get('production_card')
        place_name = request.data.get('place_name')
        movement_type = request.data.get('movement_type')
        who = request.data.get('who')
        full_sn = request.data.get('full_sn')
        
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
                raise ValidationError({"error": "Ten proces nie pozwala na rozpoczęcie produkcji przez ten endpoint."})
            
            normalized_names, printer_name = get_printer_info_from_card(production_card)

            if not product_object.sub_product:
                raise ValidationError({"error": "Obiekt nie ma przypisanego subproduktu."})
            if product_object.sub_product.name not in normalized_names:
                raise ValidationError({"error": "Nie możesz użyć tego typu pasty dla tego produktu"})
            
            handler = MovementHandler.get_handler(movement_type, product_object, place, process, who, printer_name=printer_name)
            handler.execute()
            
            LastProductOnPlace.objects.create(product_process=process, place=place, p_type=product_object.sub_product, name_of_productig_product=printer_name)
            
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
        
        current_time = timezone.now()
        today = date.today()

        expired_conditions = Q(
            exp_date_in_process__lt=today
        ) | Q(
            max_in_process__isnull=False,
            max_in_process__lt=current_time 
        )
        expired_ids = list(
            ProductObject.objects.filter(
                expired_conditions,
                current_place_id__in=place_ids
            ).values_list("current_place_id", flat=True).distinct()
        )
        places_with_expired = list(
            Place.objects.filter(id__in=expired_ids).values_list("name", flat=True)
        )
        expired_any = bool(expired_ids)

        msg_obj = MessageToApp.objects.filter(
            line__in=place_ids,
            send=False,
            when_trigger__lte=timezone.now()
        ).order_by("when_trigger").first()

        message_to_send = msg_obj.message if msg_obj else ""
        if msg_obj:
            msg_obj.send = True
            msg_obj.save()

        per_place_flags = dict(
            AppToKill.objects.filter(line_name_id__in=place_ids)
            .values_list("line_name_id", "killing_flag")
        )
        kill_any = any(per_place_flags.values()) if per_place_flags else False
        
        group_obj = PlaceGroupToAppKill.objects.get(name=group_name)
        group_obj.last_check = timezone.now()
        group_obj.save()

        return Response({
            "group": group_name,
            "expired": expired_any,
            "places_with_expired": places_with_expired,
            "kill": kill_any,
            "per_place": per_place_flags,
            "message": message_to_send
        }, status=200)
        

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

        place_name = serializer.validated_data['place_name']
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
                    
                    if serial_type == 'karton':
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

        place_name = mother.current_place.name if mother.current_place else None

        if not process.starts:
            raise ValidationError("To nie jest process startowy")

        try:
            with transaction.atomic():
                if place_name and mother.current_place:
                    try:
                        place_obj = Place.objects.get(name=place_name, process=process)
                    except Place.DoesNotExist:
                        raise ValidationError("Takie miejsce nie istnieje")
                else:
                    place_obj = None
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
                    
                    existing_children_count = ProductObject.objects.filter(
                        mother_object=mother,
                        sub_product=sub_product_obj
                    ).count()

                    if sub_product_obj.child_limit is not None and existing_children_count >= sub_product_obj.child_limit:
                        raise ValidationError(
                            f"Przekroczono limit {sub_product_obj.child_limit} dla SubProduct '{sub_product_obj.name}' (matka {mother.full_sn})."
                        )

                    product_object = ProductObject(
                        full_sn=full_sn,
                        product=product,
                        sub_product=sub_product_obj,
                        serial_number=serial_number,
                        production_date=production_date,
                        expire_date=expire_date,
                        current_place=place_obj,
                        current_process=process,
                        exp_date_in_process = mother.exp_date_in_process if mother else None,
                        quranteen_time = mother.quranteen_time if mother else None,
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
    

class ListGroupsStatuses(ListAPIView):
    serializer_class = PlaceGroupToAppKillSerializer
    queryset = PlaceGroupToAppKill.objects.all()
    ordering = ["name"]


class SubProductsCounter(ListAPIView):
    def get(self, request, *args, **kwargs):
        product_id = request.query_params.get("product_id")
        process_uuid = request.query_params.get("process_uuid")

        if not product_id or not process_uuid:
            return Response(
                {"detail": "Brak wymaganych parametrów: product_id, process_uuid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Filtruj ProductObject
        queryset = (
            ProductObject.objects.filter(
                product_id=product_id,
                current_process_id=process_uuid,
                current_place__isnull=False,
            )
            .values("sub_product__name")
            .annotate(count=Count("id"))
        )

        result = {}
        for row in queryset:
            name = row["sub_product__name"] or "Brak sub produktu"
            result[name] = row["count"]

        return Response(result, status=status.HTTP_200_OK)
    

class RetoolingView(GenericAPIView):
    serializer_class = RetoolingSerializer

    def post(self, request, *args, **kwargs):
        process_uuid = self.kwargs.get('process_uuid')

        ser = self.serializer_class(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        place_name = data["place_name"]
        movement_type = data["movement_type"]
        who = data["who"]
        production_card = data["production_card"]

        
        process = ProductProcess.objects.get(id=process_uuid)
        place = Place.objects.filter(name=place_name, process=process).first()

        if not place:
            raise ValidationError({"error": "Nie znaleziono miejsca dla danego procesu."})

        try:
            kill_flag = AppToKill.objects.get(line_name=place)
        except AppToKill.DoesNotExist:
            raise ValidationErrorWithCode(
                message="AppKill nie istnieje dla danego miejsca.",
                code="app_kill_no_exist"
            )

        kill_flag.killing_flag = True
        kill_flag.save()

        if movement_type != "retooling":
            raise ValidationError({"error": "Nieprawidłowy typ ruchu (oczekiwano 'retooling')."})

        if not production_card:
            raise ValidationError({"error": "Bez karty nie możemy pójść dalej."})

        normalized_names, printer_name = get_printer_info_from_card(production_card)

        try:
            product_object = ProductObject.objects.get(current_process=process, current_place=place)
        except:
            raise ValidationError({"error": "Nie można przezbroic bo w środku nie ma pasty"})
        
        today = timezone.localdate()
        expiry = product_object.exp_date_in_process or product_object.expire_date

        if expiry and expiry < today:
            raise ValidationError({"error": "Obiekt jest przeterminowany"})

        if not product_object.sub_product:
            raise ValidationError({"error": "Obiekt nie ma przypisanego subproduktu."})

        if product_object.sub_product.name not in normalized_names:
            raise ValidationError({"error": "Nie możesz użyć tego typu pasty dla tego produktu."})
        
        last_production = (
            LastProductOnPlace.objects
            .filter(product_process=process, place=place)
            .order_by('-date')
            .first()
        )

        if not last_production:
            raise ValidationErrorWithCode(
                message="Brak historii pasty na tym stanowisku.",
                code="NO_PASTE_HISTORY"
            )

        if last_production.p_type.name != product_object.sub_product.name:
            raise ValidationError({"error": "Nie możesz użyć tej pasty do tego produktu – ostatnia używana była inna."})

        if kill_flag.killing_flag:
            kill_flag.killing_flag = False
            kill_flag.save()
        
        ProductObjectProcessLog.objects.create(
            product_object=product_object,
            process=process,
            entry_time=timezone.now(),
            who_entry=who,
            place=place,
            movement_type=movement_type
        )

        return Response({"success": "Objekt przezbrojony"}, status=status.HTTP_200_OK)
        

class StencilBulkCreate(APIView):
    DATA = [('S6H02', '15009319_00', 1, 'S17286'), ('S6H06', '15027557_01_TOP', 1, 'S0101301024'), ('S6H07', '15027557_01_BOT', 1, 'S0102301024'), ('S6H08', '15027558_01_TOP', 1, 'S0103301024'), ('S6H09', '15027558_01_BOT', 1, 'S0104301024'), ('S6H10', '15024068_07', 1, 'S1001170625'), ('S6S001', '15010832', 1, '#0501170921'), ('S6S002', '15011087_02', 1, 'S05538'), ('S6S003', '15011087_02', 1, 'S07491'), ('S6S004', '15021193_00', 1, 'S26106'), ('S6S005', '15021048_02', 1, 'S27964'), ('S6S006', '15020963_02', 1, 'S25518'), ('S6S007', '15020617_01_BOT', 1, 'S23815'), ('S6S008', '15020617_01_TOP', 1, 'S23814'), ('S6S009', '15020919_00_BOT', 1, 'S23666'), ('S6S010', '15020919_01_TOP', 1, 'S23665'), ('S6S011', '15020470_02', 1, 'S25200'), ('S6S012', '15010958_04_BOT', 1, 'S06478'), ('S6S013', '15013415_00', 1, 'S17612'), ('S6S014', '15016856_02', 1, 'S18883'), ('S6S015', '15016856_02', 1, 'S18969'), ('S6S017', '15016616_04_TOP', 1, 'S0301180923'), ('S6S018', '15016616_04_TOP', 1, 'S0302180923'), ('S6S019', '15015302_00_BOT', 1, 'TR424'), ('S6S020', '15015302_00_TOP', 1, '#0301180521'), ('S6S021', '15015302_00_TOP', 1, '#0302180521'), ('S6S022', '15021403_00_BOT', 1, 'S0201240223'), ('S6S023', '15021403_00_TOP', 1, 'S0801200123'), ('S6S024', '15021403_00_TOP', 1, 'S0203240223'), ('S6S025', '15012487_03_BOT', 1, 'S16156'), ('S6S026', '15012487_03_BOT', 1, 'S12551'), ('S6S027', '15012487_03_TOP', 1, '#1201140322'), ('S6S028', '15012487_03_TOP', 1, 'S0601061221'), ('S6S029', '15021457_00', 1, 'S20923'), ('S6S030', '15009713_05', 1, 'S07099'), ('S6S031', '15009713_05', 1, 'S12553'), ('S6S032', '15010321_01', 1, 'S04734'), ('S6S033', '15010322_00', 1, 'S04733'), ('S6S034', '15024425_00', 1, 'S27683'), ('S6S036', '15022956_00', 1, 'S26109'), ('S6S037', '15021714_02', 1, 'S30304'), ('S6S038', '15006526_02_TOP', 1, 'S16767'), ('S6S039', '15006526_02_BOT', 1, 'S16768'), ('S6S040', '15006526_01_BOT', 1, 'S05881'), ('S6S041', '15011435_01', 1, 'S07512'), ('S6S042', '15012964_00', 1, 'S08937'), ('S6S043', '15012963_00', 1, 'S08938'), ('S6S044', '15010742_00', 
1, 'S07509'), ('S6S045', '15008517_03', 1, 'S04362'), ('S6S046', '15023082_00_BOT', 1, 'S23504'), ('S6S047', '15023082_00_TOP', 1, 'S23503'), ('S6S048', '15016855_02', 1, '#0602200921'), ('S6S049', '15016855_01', 1, 'S16002'), ('S6S050', '15016855_02', 1, '#0601200921'), ('S6S051', '15009716_01', 1, 'S06479'), ('S6S052', '15017349_00', 1, 'S15654'), ('S6S053', '15012486_03', 1, '#0604220721'), ('S6S054', '15012486_03', 1, '#0605220721'), ('S6S055', '15015647_00', 1, 'S18180'), ('S6S056', '15015648_00_TOP', 1, 'S18281'), ('S6S057', '15015648_00_BOT', 1, 'S16127'), ('S6S058', '15015648_00_BOT', 1, 'S13156'), ('S6S059', '15015648_00_TOP', 1, 'S0701201224'), ('S6S060', '15022746_01', 1, 'S22231'), ('S6S061', '15021804_00', 1, 'S19573'), ('S6S062', '15021803_00', 1, 'S19653'), ('S6S063', '15021802_00_BOT', 1, 'S19576'), ('S6S064', '15021802_00_TOP', 1, 'S19575'), ('S6S065', '15023158_00_BOT', 1, 'S23674'), ('S6S066', '15023158_00_TOP', 1, 'S23673'), ('S6S067', '15021801_00', 1, 'S19574'), ('S6S068', '15023159_00_BOT', 1, 'S24313'), ('S6S069', '15023159_00_TOP', 1, 'S30771'), ('S6S070', '15024216_00', 1, 'S32071'), ('S6S072', '15024013_00', 1, 'S27375'), ('S6S073', '15020581_02_BOT', 1, 'S25743'), ('S6S074', '15020581_02_TOP', 1, 'S25742'), ('S6S075', '15023387_02_BOT', 1, 'S27130'), ('S6S076', '15023387_02_TOP', 1, 'M0402270224'), ('S6S077', '15023421_00', 1, 'S25912'), ('S6S078', '15020631_01_BOT', 1, 'S25745'), ('S6S079', '15020631_01_TOP', 1, 'S25744'), ('S6S080', '15023194_02_BOT', 1, 'S25747'), ('S6S081', '15023194_02_TOP', 1, 'S0702180424'), ('S6S082', '15024223_01', 1, 'S26427'), ('S6S083', '15025311_03_BOT', 1, 'S0102040724'), ('S6S084', '15025311_03_TOP', 1, 'W0101040724'), ('S6S096', '15029763_00_TOP', 1, 'TY9221'), ('S6S097', '15029763_00_BOT', 1, 'TY9222'), ('S6S098', '15029765_00_TOP', 1, 'TY9223'), ('S6S099', '15029765_00_BOT', 1, 'TY9224'), ('S6S100', '15029766_01_TOP', 1, 'TY9225'), ('S6S101', '15030284_00_TOP', 1, 'TY09367'), ('S6S102', '15028520_02_BOT', 1, 'TY05901'), ('S6S103', '15028520_02_TOP', 1, 'S0801180725'), ('S6S104', '15030801_00_TOP', 1, 'TY12230'), ('S6S106', '15027838_02_BOT', 1, 'TY00334'), ('S6S107', '15027838_02_TOP', 1, 'TY00333'), ('S6S108', '15027837_00_BOT', 1, 'TX14490'), ('S6S109', '15027837_00_TOP', 1, 'TX14489'), ('S6S110', '15028036_02_BOT', 1, 'TX14486'), ('S6S111', '15028792_00_TOP', 1, 'S0801170225'), ('S6S112', '15028792_00_TOP', 1, 'S0802170225'), ('S6S113', '15028792_00_BOT', 1, 'TY01993'), ('S6S114', '15028792_00_TOP', 1, 'TY01992'), ('S6S115', '15028683_03_BOT', 1, 'TY05097'), ('S6S116', '15028683_03_TOP', 1, 'TY05096'), ('S6S118', '15025186_03_BOT', 1, 'S34982'), ('S6S119', '15025186_03_TOP', 1, 'S34981'), ('S6S121', '15025188_04_TOP', 1, 'S33917'), ('S6S122', '15025189_00_TOP', 1, 'S33750'), ('S6S123', '15025190_00_BOT', 
1, 'S33753'), ('S6S124', '15025190_00_TOP', 1, 'S33751'), ('S6S125', '15025183_02_BOT', 1, 'W0401141025'), ('S6S126', '15025183_02_TOP', 1, 'S34235'), ('S6S127', '15025182_02', 1, 'W0402141025'), ('S6S128', '15024081_03_BOT', 1, 'S34984'), ('S6S129', '15024081_03_TOP', 1, 'S34983'), ('S6S130', '15023980_02_BOT', 1, 'S33743'), ('S6S131', '15023980_02_TOP', 1, 'S33742'), ('S6S132', '15029346_00_BOT', 1, 'TY03743'), ('S6S133', '15028605_02_BOT', 1, 'S0601240725'), ('S6S134', '15028605_02_TOP', 1, 'TY08073'), ('S6S135', '15028383_00_TOP', 1, 'TY08133'), ('S6S136', '15029914_00', 1, 'TY07867'), ('S6S137', '15027171_01_TOP', 1, 'TX3298'), ('S6S138', '15027551_01_BOT', 1, 'TX12616'), ('S6S139', '15027552_02_BOT', 1, 'TY06869'), ('S6S140', '15027552_02_TOP', 1, 'TY06868'), ('S6S141', '15027556_01_BOT', 1, 'TX12622'), ('S6S142', '15027556_01_TOP', 1, 'TX12621'), ('S6S143', '15028037_02_BOT', 1, 'TY02256'), ('S6S144', '15028037_02_TOP', 1, 'TY02255'), ('S6S145', '15028992_04_TOP', 1, 'TY11095'), ('S6S146', '15028985_02_TOP', 1, 'TY6064'), ('S6S147', '15028986_01_TOP', 1, 'TY6065'), ('S6S148', '15028987_02_TOP', 1, 'TY10815'), ('S6S149', '15028988_02_TOP', 1, 'TY11996'), ('S6S150', '15028989_01_BOT', 1, 'TY6070'), ('S6S151', '15028989_01_TOP', 1, 'TY6069'), ('S6S152', '15028990_01_TOP', 1, 'TY6068'), ('S6S153', '15028991_01_TOP', 1, 'TY6073'), ('S6S156', '15028992_03_TOP', 1, 'TY6074'), ('S6S157', '15029253_00_BOT', 1, 'TY04453'), ('S6S158', '15029253_00_TOP', 1, 'TY04452'), ('S6S159', '15029569_00_BOT', 1, 'TY05323'), ('S6S160', '15029569_00_TOP', 1, 'TY05322'), ('S6S161', '15028527_02_BOT', 1, 'TY00780'), ('S6S162', '15028527_02_TOP', 1, 'TY00779'), ('S6S163', '15028695_01_BOT', 1, 'TY00782'), ('S6S164', '15028695_01_TOP', 1, 'TY00781'), ('S6S165', '15025050_07_BOT', 1, 'TY11608'), ('S6S166', '15025050_07_TOP', 1, 'TY11607'), ('S6S167', '15900572_00_BOT', 1, 'S1401201025'), ('S6S168', '15900572_00_TOP', 1, 'S0403141025'), ('S6S169', '15029252_00_TOP', 1, 'S0407141025'), ('S6S170', '15029249_00_BOT', 1, 'TY05140'), ('S6S171', '15029249_00_TOP', 1, 'TY05139'), ('S6S172', '15029250_00_BOT', 1, 'TY05135'), ('S6S173', '15029250_00_TOP', 1, 'TY05134'), ('S6S175', '15028331_00_TOP', 1, 'TY10536'), ('S6S176', '15900572_00_BOT', 1, 'TY11167'), ('S6S177', '15900572_00_TOP', 1, 'TY11166'), ('S6S178', '15030805_00_TOP', 1, 'TY12505'), ('S6S179', '15030806_00_TOP', 1, 'TY12508'), ('S6S180', '15030877_00_TOP', 1, 'TY12510'), ('S6S181', '15030878_00_TOP', 1, 'TY12511'), ('S6S182', '15031134_00_BOT', 1, 'TY13134'), ('S6S183', '15031134_00_TOP', 1, 'TY13133'), ('S6S195', '15028985_00_TOP', 1, 'TX02371'), ('S6S196', '15028986_00_TOP', 1, 'TY02372'), ('S6S198', '15028988_01_TOP', 1, 'TY02386'), ('S6S199', '15028989_00_BOT', 1, 'TY02362'), ('S6S200', '15028989_00_TOP', 1, 'TY02361'), ('S6S201', '15028990_00_TOP', 1, 'TY02370'), ('S6S202', '15028991_00_TOP', 1, 'TY02373'), ('S6S203', '15028992_01_TOP', 1, 'TY02374'), ('S6S205', '15028985_01_TOP', 1, 'TY04008'), ('S6S207', '15030118_00_BOT', 1, 'TY09510'), ('S6S208', '15030118_00_TOP', 1, 'TY09509'), ('S6S209', '15030119_00_BOT', 1, 'TY09512'), ('S6S210', '15030119_00_TOP', 1, 'TY09511'), ('S6S211', '15025050_06_BOT', 
1, 'S0202081025'), ('S6S212', '15025050_06_BOT', 1, 'TY06249'), ('S6S213', '15025050_06_TOP', 1, 'S0201081025'), ('S6S214', '15025050_06_TOP', 1, 'TY06248'), ('S6S216', '15030192_00_TOP', 1, 'TY08518'), ('S6S218', '15030193_00_TOP', 1, 'TY08779'), ('S6S219', '15030194_00_BOT', 
1, 'TY08576'), ('S6S220', '15030194_00_TOP', 1, 'TY08573'), ('S6S222', '15900554_00_BOT', 1, 'TY6072'), ('S6S223', '15900554_00_TOP', 1, 'TY6071'), ('S6S224', '15030118_01_BOT', 1, 'TY10535'), ('S6S225', '15030118_01_TOP', 1, 'TY10534'), ('S6S226', '15028520_03_BOT', 1, 'S0405280825'), ('S6S227', '15028520_03_TOP', 1, 'S0406280825'), ('S8S01', '15024413_02_BOT', 1, 'S33293'), ('S8S02', '15024413_03_TOP', 1, 'S1501030624'), ('S8S03', '15024416_02', 1, 'S33294'), ('S8S04', '15013529_04', 1, 'S21799'), ('S8S05', '15013530_05_BOT', 1, 'S21802'), ('S8S06', '15013530_05_TOP', 1, 'S21801'), ('S8S07', '15006772_00', 1, 'S13527'), ('S8S08', '15022001_02', 1, 'S23105'), ('S8S09', '15012450', 1, 'S06882'), ('S8S10', '15009232_00', 1, 'S04479'), ('S8S100', '15006646_01', 1, 'S02049'), ('S8S101', '15005612_00', 1, 'S01260'), ('S8S102', '15003311_00', 1, 'S02388'), ('S8S103', '15007595_00', 1, 'S09151'), ('S8S104', '15006375_00', 1, 'S01568'), ('S8S105', '15002787_02', 1, 'S06315'), ('S8S106', '15007592_00', 1, 'S04436'), ('S8S107', '15006473_00', 1, 'S01724'), ('S8S108', '15004986_00', 1, 'S07984'), ('S8S109', '15016701_00', 1, 'S13886'), ('S8S11', '15012551_00', 1, 'S0101280824'), ('S8S110', '15009505_01', 1, 'S0606260124'), ('S8S111', '15009109_00', 1, 'S03635'), ('S8S112', '15008686_01', 1, 'S0402011223'), ('S8S113', '15009893_03', 1, 'S0607260124'), ('S8S114', '15009893_03', 1, 'S0608260124'), ('S8S115', '15002375_03', 1, 'S01797'), ('S8S116', '15007593_00', 1, 'S03227'), ('S8S117', '15009077_16szt', 1, 'S05937'), ('S8S118', '15002970_00', 1, 'TI1125'), ('S8S119', '15009374_00', 1, 'S05480'), ('S8S12', '15012554_00', 1, 'S17965'), ('S8S120', '15012577_00', 1, 'S08131'), ('S8S121', '15013193_00', 1, 'S10586'), ('S8S122', '15013194_01', 1, 'S1101140425'), ('S8S123', '15022165_00', 1, 'S20262'), ('S8S124', '15012576_01', 1, 'S12171'), ('S8S125', '15012575_01', 1, 'S12170'), ('S8S126', '15010714_00_TOP', 1, 'S0610260124'), ('S8S127', '15010714_00_TOP', 1, 'S0601180925'), ('S8S128', '15010714_00_BOT', 1, 'S1001040423'), ('S8S129', '15010714_00_str1', 1, 'S30746'), ('S8S13', '15008246_01', 1, 'S17963'), ('S8S130', '15023710_00', 1, 'S0701040624'), ('S8S131', '15023707_00', 1, 'S31246'), ('S8S132', '15011255_00', 1, 'S0901121124'), 
('S8S133', '15011108_02', 1, 'S15282'), ('S8S134', '15015059_00', 1, 'S11392'), ('S8S135', '15015113_00', 1, 'S11393'), ('S8S136', '15011256_00', 1, 'S05704'), ('S8S137', '15006369_02', 1, 'S02126'), ('S8S138', '15004013_01', 1, 'S0401270224'), ('S8S139', '15004166_03', 1, 'S0405141025'), ('S8S14', '15016809_00', 1, 'S13944'), ('S8S140', '15008868_00', 1, 'S10345'), ('S8S141', '15016224_01', 1, 'S14329'), ('S8S142', '15013923_00', 1, 'S0401011223'), ('S8S143', '15013923_00', 1, 'S0102171123'), ('S8S144', '15013923_00', 1, 'S12756'), ('S8S145', '15013922_00', 1, 'S0101221123'), ('S8S146', '15013922_00', 1, 'S1202250423'), ('S8S147', '15013922_00', 1, 'S1202140322'), ('S8S148', '15013921_00', 1, 'S12754'), ('S8S149', '15013921_00', 1, 'S13314'), ('S8S15', '15022695_00', 1, 'S29631'), ('S8S150', '15024434_00', 1, 'S26780'), ('S8S151', '15024383_00', 1, 'S0101181024'), ('S8S152', '15024905_00', 1, 'S28741'), ('S8S153', '15026022_03', 1, 'S35928'), ('S8S154', '15015877_01', 1, 'S0201221221'), ('S8S155', '15015876_00', 1, 'S13209'), ('S8S156', '15004167_01', 1, 'TI1380'), ('S8S157', '15016670_01', 1, 'S29713'), ('S8S158', '15009818_01', 1, 'S11900'), ('S8S159', '15009818_01', 1, 'S05427'), ('S8S16', '15022695_00', 1, 'S29632'), ('S8S160', '15002314_02', 1, 'TE0495'), ('S8S161', '15005984_00', 1, 'S08747'), ('S8S162', '15005984_00', 1, 'S09462'), ('S8S163', '15013027_01', 1, 'S11236'), ('S8S164', '15014372_00', 1, '#1203140322'), ('S8S165', '15014961_02', 1, 'S0602260124'), ('S8S166', '15026183_01', 1, 'S34489'), ('S8S167', '15014175_00', 1, 'S15540'), ('S8S168', '15014175_00', 1, 'S0501231023'), ('S8S169', '15016484_00', 1, 'S13312'), ('S8S17', '15015770_00', 1, 'S13039'), ('S8S170', '15024069_02_BOT', 1, 'S0801090525'), ('S8S171', '15023110_03_BOT', 1, 'S26202'), ('S8S172', '15023110_03_TOP', 1, 'S26201'), ('S8S173', '15023056_02_BOT', 1, 'S27374'), ('S8S174', '15023056_02_TOP', 1, 'S27373'), ('S8S175', '15023057_03_BOT', 1, 'S32740'), ('S8S176', '15023057_03_TOP', 1, 'S32739'), ('S8S177', '15016811_00_BOT', 1, 'S14399'), ('S8S178', '15016811_00_TOP', 1, 'S14398'), ('S8S179', '15010564_02_BOT', 1, 'S06311'), ('S8S18', '15015770_00', 1, 'S0401270223'), ('S8S180', '15010564_02_TOP', 1, 'S06312'), ('S8S181', '15010565_01', 1, 'S05828'), ('S8S182', '15026214_02', 1, 'S34170'), ('S8S183', '15006387_00_BOT', 1, 'S02849'), ('S8S184', '15006387_00_TOP', 1, 'S09344'), ('S8S185', '15014161_00_BOT', 1, 'S10383'), ('S8S186', '15014161_00_TOP', 1, 'S10382'), ('S8S187', '15007791_BOT', 1, 'S04529'), ('S8S188', '15007791_TOP', 1, 'S04527'), ('S8S189', '15024605_00_BOT', 1, 'S28077'), ('S8S19', '15015769_01', 1, '#11012100222'), ('S8S190', '15024605_00_TOP', 1, 'S28076'), ('S8S191', '15024604_00_BOT', 1, 'S28909'), ('S8S192', '15024604_00_TOP', 1, 'S28908'), ('S8S193', '15020221_00_BOT', 1, 'S15559'), ('S8S194', '15020221_00_TOP', 1, 'S15558'), ('S8S195', '15017206_00_BOT', 1, 'S15560'), ('S8S196', '15017206_01_TOP', 1, 'TX6014'), ('S8S197', '15007690_02', 1, 'S05882'), ('S8S198', '15007692_04_BOT', 1, 'S05890'), ('S8S199', '15007692_04_TOP', 1, 'S05889'), ('S8S20', '15015769_01', 1, 'S17279'), ('S8S200', '15012336_00', 1, 'S07239'), ('S8S201', '15006302_05', 1, 'S05535'), ('S8S202', '15011957_00', 1, 'S06625'), ('S8S203', '15006301_03', 1, 'S05536'), ('S8S204', '15006300_03_BOT', 1, 'R/12440'), ('S8S205', '15006300_03_TOP', 1, 'S09658'), ('S8S206', '15022047_00', 1, 'S29742'), ('S8S207', '15005909_BOT', 1, 'S05817'), ('S8S208', '15005909_06_TOP', 1, 'S03637'), ('S8S209', '15005910_03_BOT', 1, 'S0101220424'), ('S8S21', '15024838_01', 1, 'S29930'), ('S8S210', '15005910_03_TOP', 1, 'S0102220424'), ('S8S211', '15005908_06_BOT', 1, '#0202290921'), ('S8S212', '15005908_06_TOP', 1, '#0201290921'), ('S8S213', '15010111_01_BOT', 1, 'S07299'), ('S8S214', '15010111_01_TOP', 1, 'S07298'), ('S8S215', '15010108_02', 1, 'S07296'), ('S8S216', '15010109_03', 1, 'S11932'), ('S8S217', '15005594_04_BOT', 1, 'R/12436'), ('S8S218', '15005594_04_TOP', 1, 'R/12435'), ('S8S219', '15005596_09', 1, 'S03630'), ('S8S22', '15021088_04', 1, 'S25841'), ('S8S220', '15005595_06', 1, 'S03629'), ('S8S221', '15008067_02', 1, 'S03634'), ('S8S222', '15008066', 1, 'S03633'), ('S8S223', '15012236_00', 1, 'S0701180424'), ('S8S224', '15012335_00', 1, 'S1001170524'), ('S8S225', '15011956_00', 1, 'S06626'), 
('S8S226', '15010578_01_BOT', 1, 'S06624'), ('S8S227', '15010578_01_TOP', 1, 'S06623'), ('S8S228', '15005289_00_BOT', 1, 'S06421'), ('S8S229', '15005289_TOP', 1, 'S06407'), ('S8S23', '15021184_01', 1, 'S19929'), ('S8S230', '15016844_00_BOT', 1, 'S18610'), ('S8S231', '15016844_00_TOP', 1, 'S18609'), ('S8S232', '15021223_00', 1, 'S23699'), ('S8S233', '15021694_00_BOT', 1, 'S19377'), ('S8S234', '15021694_00_TOP', 1, 'S23698'), ('S8S235', '15021222_00_BOT', 1, 'S19020'), ('S8S236', '15021222_01_TOP', 1, 'TX6015'), ('S8S237', '15022845_00_BOT', 1, 'S29300'), ('S8S238', '15022845_01_TOP', 1, 'TX6017'), ('S8S239', '15022844_00_BOT', 1, 'S29298'), ('S8S24', '15008322_00', 1, 'S06422'), ('S8S240', '15022844_01_TOP', 1, 'TX6016'), ('S8S241', '15027053_01_BOT', 1, 'S35914'), ('S8S242', '15027053_01_TOP', 1, 'S35915'), ('S8S243', '15016847_00', 1, 'S18255'), ('S8S244', '15016845_00', 1, 'S18704'), ('S8S245', '15016846_00', 1, 'S18454'), ('S8S246', '15026897_00_BOT', 1, 'TX9131'), ('S8S247', '15026895_00_BOT', 1, 'TX9129'), ('S8S248', '15026896_00_BOT', 1, 'TX9130'), ('S8S249', '15026898_00_BOT', 1, 'TX9135'), ('S8S250', '15026898_00_TOP', 1, 'TX9134'), ('S8S251', '15026899_00_BOT', 1, 'TX9132'), ('S8S252', '15020380_00', 1, 'S15807'), ('S8S253', '15013286_01', 1, 'S15586'), ('S8S254', '15012841_01', 1, 'S10983'), ('S8S255', '15007535_02', 1, 'S0701230924'), ('S8S256', '15023707_00', 1, 'W0401281124'), ('S8S258', '15006785_01', 1, 'S33650'), ('S8S259', '15003687_02_BOT', 1, 'S33652'), ('S8S260', '15003687_02_TOP', 1, 'S33651'), ('S8S261', '15014042_00_BOT', 1, 'S33654'), ('S8S262', '15014042_00_TOP', 1, 'S33653'), ('S8S27', '15023382_01_BOT', 1, 'S26060'), ('S8S273', '15021198_00', 1, 'S18148'), ('S8S274', '15010013_03', 1, 'S05986'), ('S8S275', '15010013_03', 1, 'S18074'), ('S8S276', '15005265_03', 1, 'S06897'), ('S8S277', '15005046_03', 1, 'S09404'), ('S8S278', '15005117_02_BOT', 1, '#0404070416'), ('S8S279', '15005117_02_TOP', 1, '#0403070416'), ('S8S28', '15023382_01_TOP', 1, 'S26059'), ('S8S280', '15005035_01', 1, '#0402070416'), ('S8S281', '15005762_01', 1, 'S08247'), ('S8S282', '15003261_00', 1, 'S27769'), ('S8S283', '15006020_02', 1, 'S02211'), ('S8S284', '15006021_01', 1, 'S01638'), ('S8S29', '15026432_00_BOT', 1, 'S0402280825'), ('S8S30', '15026432_00_BOT', 1, 'S33436'), ('S8S31', '15026432_00_TOP', 1, 'S33435'), ('S8S32', '15016468_00_BOT', 1, '#0303020421'), ('S8S33', '15016468_01_TOP', 1, '#0701110222'), ('S8S34', '15016468_01_TOP', 1, '#0401080222'), ('S8S35', '15014474_01', 1, 'S12870'), ('S8S36', '15014474_01', 1, 'S17281'), ('S8S37', '15014475_01', 1, 'S12871'), ('S8S38', '15014475_01', 1, 'S17282'), ('S8S39', '15024817_00_BOT', 1, 'S28493'), ('S8S40', '15024817_00_BOT', 1, 'S29296'), ('S8S42', '15024817_00_TOP', 1, 'S0901180325'), ('S8S43', '15024817_00_TOP', 1, 'S1201070125'), ('S8S44', '15014476_01', 1, 'S17283'), ('S8S45', '15014477_01', 1, 'S12873'), ('S8S46', '15014477_01', 1, 'S17284'), ('S8S47', '15020659_00_BOT', 1, 'S17942'), ('S8S48', '15020659_00_TOP', 1, 'S17941'), ('S8S49', '15020658_00', 1, 'S18246'), ('S8S50', '15020656_00', 1, 'S17379'), ('S8S51', '15002829_01', 1, 'S14474'), ('S8S52', '15002828_01', 1, 'TI3427'), ('S8S53', '15002830_01', 1, 'S10655'), ('S8S54', '15014633_01', 1, 'S11396'), ('S8S55', '15014584_00', 1, 'S11422'), ('S8S56', '15024123_01', 1, 'S26711'), ('S8S57', '15024124_00', 1, 'S26710'), ('S8S58', '15025432_00_BOT', 1, 'S0602141024'), ('S8S59', '15025432_00_TOP', 1, 'S32077'), ('S8S60', '15023232_00', 1, 'S25509'), ('S8S61', '15025994_00', 1, 'S1201190224'), ('S8S62', 
'15022254_01', 1, 'S20975'), ('S8S63', '15022633_00', 1, 'S0201250924'), ('S8S64', '15022633_00', 1, 'S0403270223'), ('S8S65', '15025051_00', 1, 'S28984'), ('S8S65', '15029287', 1, 'S28984'), ('S8S66', '15017459_02', 1, 'S17210'), ('S8S67', '15026223_00', 1, 'S32938'), ('S8S68', '15024748_03', 1, 'S1203250423'), ('S8S69', '15017458_02', 1, 'S16762'), ('S8S70', '15023377_02', 1, 'S0601141024'), ('S8S71', '15024155_00', 1, 'S33928'), ('S8S72', '15024154_00', 1, 'S33927'), ('S8S73', '15023934_01', 1, 'S34193'), ('S8S74', '15022492_03', 1, 'S24486'), ('S8S75', '15022493_01', 1, 'S23505'), ('S8S76', '15023833_00', 1, 'S25245'), ('S8S77', '15023832_00', 1, 'S0101110823_S25244'), ('S8S78', '15021913_01', 1, 'S1301120923_S19592'), ('S8S79', '15021979_00', 1, 'S0801040923'), ('S8S80', '15021979_00', 1, 'S19591'), ('S8S81', '15021914_01', 1, 'S1001160623_S19593'), ('S8S82', '15017460_02', 1, 'S17211'), ('S8S83', '15023263_02', 1, 'S27611'), ('S8S84', '15023264_02', 1, 'S26907'), ('S8S85', '15026834_00', 1, 'S35190'), ('S8S86', '15027719_00', 1, 'TX9133'), ('S8S88', '15015217_02', 1, 'S14096'), ('S8S89', '15021683_01', 1, 'S26712'), ('S8S90', '15006311_01', 1, 'S0502220124'), ('S8S91', '15006311_01', 1, 'S1301240124'), ('S8S92', '15006489_01', 1, 'S06423'), ('S8S93', '15008687_00', 1, 'S13810'), ('S8S94', 
'15008687_00', 1, 'S24950'), ('S8S95', '15007572_00', 1, 'S1201120925'), ('S8S96', '15007594_01', 1, 'S0603260124'), ('S8S97', '15007594_01', 1, 'S0604260124'), ('S8S98', '15007700_01', 1, 'S0601260124'), ('S8S99', '15002259_01', 1, 'S27992'), ('S9S03', '15006295_03', 1, 'S15367'), ('S9S04', '15005750_05', 1, 'S09461'), ('S9S05', '15009129_01', 1, 'S04251'), ('S9S06', '15022952_00', 1, 'S0901091224'), ('S9S07', '15022953_03_BOT', 1, 'S0301100725'), ('S9S08', '15022953_03_TOP', 1, 'S26319'), ('S9S09', '15022954_00', 1, 'S24085'), ('S9S10', '15024746_00_BOT', 
1, 'S27720'), ('S9S100', '15022676_02_BOT', 1, 'S24799'), ('S9S101', '15022676_02_TOP', 1, 'S24798'), ('S9S102', '15022677_01', 1, 'S22137'), ('S9S103', '15022678_02_BOT', 1, 'S22408'), ('S9S104', '15022678_02_TOP', 1, 'S22407'), ('S9S105', '15022679_01', 1, 'S22138'), ('S9S106', '15022680_01_BOT', 1, 'S22420'), ('S9S107', '15022680_01_TOP', 1, 'S22419'), ('S9S108', '15022681_01_BOT', 1, 'S22411'), ('S9S109', '15022681_01_TOP', 1, 'S22410'), ('S9S11', '15024746_00_TOP', 1, 'S27719'), ('S9S110', '15022682_01_BOT', 1, 'S24702'), ('S9S111', '15022682_01_TOP', 1, 'S22421'), ('S9S112', '15022683_02_BOT', 1, 'S24909'), ('S9S113', '15022683_02_TOP', 1, 'S24908'), ('S9S114', '15022557_02_BOT', 1, 'S22912'), ('S9S115', '15022557_02_TOP', 1, 'S22911'), ('S9S116', '15022560_03_TOP', 1, 'S23671'), ('S9S117', '15022560_03_BOT', 1, 'S24735'), ('S9S118', '15022561_01', 1, 'S22919'), ('S9S119', '15022559_03_BOT', 1, 'S25771'), ('S9S12', '15024747_00_BOT', 1, 'S0601110324'), ('S9S120', '15022559_03_TOP', 1, 'S23669'), ('S9S121', '15022558_02_BOT', 1, 'S23249'), ('S9S122', '15022558_02_TOP', 1, 'S23248'), ('S9S123', '15027185_02_BOT', 1, 'TX9847'), ('S9S124', '15027185_02_TOP', 1, 'TX9846'), ('S9S125', '15027186_02_BOT', 1, 'TX9849'), ('S9S126', '15027186_02_TOP', 1, 'TX9848'), ('S9S127', '15027604_01_TOP', 1, 'TX7761'), ('S9S13', '15024747_00_TOP', 1, 'S27721'), ('S9S14', '15012327_00', 1, 'S13273'), ('S9S15', '15015332_01', 1, 'S13486'), ('S9S16', '15015333_01', 1, 'S13487'), ('S9S165', '15025646_03_BOT', 1, 'S34110'), ('S9S166', '15025646_03_TOP', 1, 'S34109'), ('S9S167', '15025647_03_BOT', 1, 'S34112'), ('S9S168', '15025647_03_TOP', 1, 'S34111'), ('S9S169', '15025648_03', 1, 'S34113'), ('S9S17', '15015335_01', 1, 'S13489'), ('S9S170', '15025649_03', 1, 'S34114'), ('S9S171', '15020559_01', 1, 'S17912'), ('S9S172', '15020558_01', 1, 'S17911'), ('S9S173', '15020556_01_BOT', 1, 'S17830'), ('S9S174', '15020556_01_TOP', 1, 'S17829'), ('S9S175', '15020557_01_BOT', 1, 'S17832'), ('S9S176', '15020557_01_TOP', 1, 'S17831'), ('S9S177', '15020554_01_BOT', 1, 'S17922'), ('S9S178', '15020554_01_TOP', 1, 'S17921'), ('S9S179', '15020555_02_BOT', 1, 'S17924'), ('S9S18', '15015334_01', 1, 'S13488'), ('S9S180', '15020555_02_TOP', 1, 'S17923'), ('S9S181', '15020560_00', 1, 'S17847'), ('S9S182', '15020561_00', 1, 'S17848'), ('S9S183', '15020567_00', 1, '#0601190422'), ('S9S184', '15020566_01', 1, 'S17913'), ('S9S185', '15020562_01_BOT', 1, 'S17926'), ('S9S186', '15020562_01_TOP', 1, '#1202131021'), ('S9S187', '15020563_01_BOT', 1, 'S17928'), ('S9S188', '15020563_01_TOP', 1, '#1201131021'), ('S9S189', '15020564_01_BOT', 
1, 'S17929'), ('S9S19', '15015331_00_BOT', 1, 'S11965'), ('S9S190', '15020564_01_TOP', 1, 'S17930'), ('S9S191', '15020565_01_BOT', 1, 'S17932'), ('S9S192', '15020565_01_TOP', 1, 'S17931'), ('S9S193', '15020548_01', 1, 'S17845'), ('S9S194', '15020549_01', 1, 'S17846'), ('S9S195', '15020546_02', 1, 'S17909'), ('S9S196', '15020547_02', 1, 'S17910'), ('S9S197', '15020542_01_BOT', 1, 'S17842'), ('S9S198', '15020542_01_TOP', 1, 'S17841'), ('S9S199', '15020543_01_BOT', 1, 'S17830_S17844'), ('S9S20', '15015331_01_TOP', 1, 'S12863'), ('S9S200', '15020543_01_TOP', 1, 
'S0601160724'), ('S9S201', '15020551_00', 1, 'S17847'), ('S9S202', '15020550_00', 1, 'S17907'), ('S9S203', '15020552_00', 1, 'S17828'), ('S9S204', '15020553_01', 1, 'S17906'), ('S9S205', '15022562_03', 1, 'S23780'), ('S9S206', '15022563_02_BOT', 1, 'S23868'), ('S9S207', '15022563_02_TOP', 1, 'S23867'), ('S9S208', '15022564_02_BOT', 1, 'S1301101023'), ('S9S209', '15022564_02_TOP', 1, 'S32190'), ('S9S21', '15015330_00_BOT', 1, 'S11963'), ('S9S210', '15022656_01_BOT', 1, 'S22883'), ('S9S211', '15022566_01_BOT', 1, 'S22885'), ('S9S212', '15022566_01_TOP', 1, 'S22884'), ('S9S213', '15023066_02_BOT', 1, 'S27714'), ('S9S214', '15023066_02_TOP', 1, 'S27713'), ('S9S215', '15022702_03_BOT', 1, 'S1001201123'), ('S9S216', '15022702_03_TOP', 1, 'S27712'), ('S9S217', '15024691_00_BOT', 1, 'S23872'), ('S9S218', '15024691_00_TOP', 1, 'S0402270223'), ('S9S219', '15023060_02', 1, 'S24625'), ('S9S22', '15015330_01_TOP', 1, 'S12862'), ('S9S220', 
'15023081_00_BOT', 1, 'S23180'), ('S9S221', '15023081_01_TOP', 1, 'S24626'), ('S9S222', '15023083_00_BOT', 1, 'S23182'), ('S9S223', '15023083_01_TOP', 1, 'S24627'), ('S9S224', '15023085_00_BOT', 1, 'S23186'), ('S9S225', '15023085_01_TOP', 1, 'S24633'), ('S9S226', '15023084_01_BOT', 1, 'S24628'), ('S9S227', '15023084_00_TOP', 1, 'S23183'), ('S9S228', '15024222_00', 1, 'S26245'), ('S9S229', '15023515_01_BOT', 1, 'S26242'), ('S9S23', '15016071_01', 1, 'S16390'), ('S9S230', '15023515_01_TOP', 1, 'S32271'), ('S9S231', '15024221_01_BOT', 1, 'S28655'), ('S9S232', '15024221_01_TOP', 1, 'S28654'), ('S9S233', '15024942_01_BOT', 1, 'S31531'), ('S9S234', '15024942_00_TOP', 1, 'S28317'), ('S9S235', '15024942_01_TOP', 1, 'S31532'), ('S9S236', '15025246_00_BOT', 1, 'S30995'), ('S9S237', '15025246_00_TOP', 1, 'S30994'), ('S9S238', '15024945_01_BOT', 1, 'S30993'), ('S9S239', '15024945_01_TOP', 1, 'S30992'), ('S9S24', '15016070_01', 1, 'S16389'), ('S9S240', '15024944_01_BOT', 1, 'S30991'), ('S9S241', '15024944_01_TOP', 1, 'S30990'), ('S9S242', '15024775_01_BOT', 1, 'S30025'), ('S9S243', '15024775_01_TOP', 1, 'S0201211124'), ('S9S244', '15024777_01_BOT', 1, 'S30027'), ('S9S245', '15024777_01_TOP', 1, 'S30026'), ('S9S246', '15024781_01_BOT', 1, 'S30029'), ('S9S247', '15024781_01_TOP', 1, 'S30028'), ('S9S248', '15025436_00_BOT', 1, 'S30031'), ('S9S249', '15025436_01_TOP', 1, 'S0401020724'), ('S9S25', '15016072_01_BOT', 1, 'S14328'), ('S9S250', '15026977_01', 1, 'S35957'), ('S9S251', '15026919_00', 1, 'S35574'), ('S9S252', '15026990_00', 1, 'S0701031025'), ('S9S253', '15026368_02_BOT', 1, 'S35207'), ('S9S254', '15026368_02_TOP', 1, 'S35208'), ('S9S255', '15026371_01_BOT', 1, 'S35209'), ('S9S256', '15026371_01_TOP', 1, 'S35210'), ('S9S257', '15026372_01_BOT', 1, 'S35211'), ('S9S258', '15026372_01_TOP', 1, 'S35212'), ('S9S259', '15026375_02_BOT', 1, 'S35941'), ('S9S26', '15016072_01_TOP', 1, 'S14327'), ('S9S260', '15026375_02_TOP', 1, 'S35940'), ('S9S261', '15026376_02_BOT', 1, 'S35213'), ('S9S262', '15026376_02_TOP', 1, 'S35214'), ('S9S263', '15027221_00', 1, 'S35936'), ('S9S264', '15026367_02', 1, 'S35206'), ('S9S265', '15026502_02_BOT', 1, 'S35215'), ('S9S266', '15026502_02_TOP', 1, 'S35216'), ('S9S267', '15026503_01_BOT', 1, 'S35217'), 
('S9S268', '15026503_01_TOP', 1, 'S35218'), ('S9S269', '15026843_00', 1, 'S35939'), ('S9S27', '15014696_02', 1, 'S13492'), ('S9S270', '15027238_00_BOT', 1, 'S35938'), ('S9S271', '15027238_00_TOP', 1, 'S35937'), ('S9S272', '15027697_00', 1, 'TX6997'), ('S9S273', '15027698_00_BOT', 1, 'TX7003'), ('S9S274', '15027698_00_TOP', 1, 'TX6998'), ('S9S275', '15027699_00_BOT', 1, 'TX7189'), ('S9S276', '15027699_00_TOP', 1, 'TX7188'), ('S9S277', '15027700_00_BOT', 1, 'TX7008'), ('S9S278', '15027700_00_TOP', 1, 'TX7006'), ('S9S279', '15027701_00_BOT', 1, 'TX7013'), ('S9S28', '15020073_00', 1, 'S15988'), ('S9S280', '15027701_00_TOP', 1, 'TX7010'), ('S9S281', '15027702_01_BOT', 1, 'TX9124'), ('S9S282', '15027702_01_TOP', 1, 'TX9123'), ('S9S283', '15027703_00_BOT', 1, 'TX7197'), ('S9S284', '15027703_00_TOP', 1, 'TX7196'), ('S9S285', '15027704_00_BOT', 1, 'TX7016'), ('S9S286', '15027704_00_TOP', 1, 'TX7014'), ('S9S287', '15027705_00', 1, 'TX7017'), ('S9S288', '15027706_00', 1, 'TX7021'), ('S9S29', '15020075_00', 1, 'S15990'), ('S9S30', '15020072_00', 1, 'S0102180324'), ('S9S31', '15024776_00_TOP', 1, 'S28396'), ('S9S32', '15020074_00', 1, 'M0101180324'), ('S9S33', '15020083_00_BOT', 1, 'S15984'), ('S9S34', '15020083_00_TOP', 1, 'S15983'), ('S9S35', '15020082_00_BOT', 1, 'S15982'), ('S9S36', '15020082_00_TOP', 1, 'S15981'), ('S9S37', '15020079_00', 1, '#1204131021'), ('S9S38', '15020078_00', 1, '#1203131021'), ('S9S39', '15020077_00_BOT', 1, 'S15976'), ('S9S40', '15020077_00_BOT', 1, 'S14731'), ('S9S41', '15020077_00_TOP', 1, 'S15975'), ('S9S42', '15020077_00_TOP', 1, 'S14730'), ('S9S43', '15020076_00_BOT', 1, 'S15974'), ('S9S44', '15020076_00_BOT', 1, 'S14729'), ('S9S45', '15020076_00_TOP', 1, 'S15973'), ('S9S46', '15020076_00_TOP', 1, 'S14728'), ('S9S47', '15020081_00', 1, 'S15980'), ('S9S48', '15020080_00', 1, 'S15979'), ('S9S49', '15014697_02', 1, 'S13211'), ('S9S50', '15014392_00_BOT', 1, 'S11718'), ('S9S51', '15014392_01_TOP', 1, 'S12748'), ('S9S52', '15014389_00_BOT', 1, 'S11712'), ('S9S53', '15014389_01_TOP', 1, 'S12747'), ('S9S54', '15014391_00_BOT', 1, 'S12189'), ('S9S55', '15014391_01_TOP', 1, 'S12750'), ('S9S56', '15014390_00_BOT', 1, 'S11714'), ('S9S57', '15014390_01_TOP', 1, 'S12749'), ('S9S58', '15014386_00_BOT', 1, 'S11706'), ('S9S59', '15014386_01_TOP', 1, 'S12686'), ('S9S60', '15014385_01_BOT', 1, 'S0402030423'), ('S9S61', '15014385_01_TOP', 1, 'S0401030423'), ('S9S62', '15014388_00_BOT', 1, 'S11710'), ('S9S63', '15014388_01_TOP', 1, 'S12688'), ('S9S64', '15014387_00_BOT', 1, 'S11708'), ('S9S65', '15014387_01_TOP', 1, 'S12689'), ('S9S66', '15022140_00', 1, 'S20286'), ('S9S67', '15022139_00_BOT', 1, 'S20285'), ('S9S68', '15022139_00_TOP', 1, 'S20477'), ('S9S69', '15012756_01', 1, 'S1201110725'), ('S9S70', '15016241_00', 1, 'S15655'), ('S9S71', '15016127_01_BOT', 1, 'S0101160725'), ('S9S72', '15016127_01_TOP', 1, 'S0102160725'), ('S9S73', '15004041_03', 1, 'S02258'), ('S9S74', '15003154_01', 1, 'S02416'), ('S9S75', '15002356_01', 1, 'S02414'), ('S9S76', '15003814_01', 1, 'S02417'), ('S9S77', '15008691_00', 1, 'S03384'), ('S9S78', '15007581_01', 1, 'S04561'), ('S9S79', '15007580_02', 1, 'S04560'), ('S9S80', '15005232_15005234', 1, 'S11901'), ('S9S81', '15006643_00', 1, 'S02420'), ('S9S82', '15023385_02_BOT', 1, 'S26431'), ('S9S83', '15023385_02_TOP', 1, 'S26430'), ('S9S84', '15006927_05', 1, 'S09026'), ('S9S85', '15024868_00_BOT', 1, 'S28513'), ('S9S86', '15024868_00_TOP', 1, 'S28512'), ('S9S87', '15024767_01', 1, 'S32159'), ('S9S88', '15024764_00', 1, 'S28891'), ('S9S89', '15024765_00', 1, 'S28892'), ('S9S90', '15024870_00', 1, 'S28516'), ('S9S91', '15024785_01', 1, 'S28511'), ('S9S92', '15024784_01', 1, 'S1401260525'), ('S9S93', '15024869_00_BOT', 1, 'S28515'), ('S9S94', '15024869_00_TOP', 1, 'S28514'), ('S9S95', '15024766_00_BOT', 1, 'S28797'), ('S9S96', '15024766_00_TOP', 1, 'S32158'), ('S9S97', '15005800_00', 1, 'S02926'), ('S9S98', '15005693_00', 1, 'S02925'), ('S9S99', '15006736_01', 1, 'S02127'), ('X2X01', '15023803_00_BOT', 1, 'S28782'), ('X2X01', '15023803_00_TOP', 1, 'S28783'), ('X2X01', '15023802_02_TOP', 1, 'S28781'), ('X2X01', '15023802_02_BOT', 1, 
'S28780'), ('X2X01', '15024975_00', 1, 'S30305'), ('X2X01', '15024977_00_TOP', 1, 'S30307'), ('X2X01', '15025592_00', 1, 'S30313'), ('X2X01', '15025591_00', 1, 'S30312'), ('X2X01', '15025590_00', 1, 'S30311')]
    
    def post(self, request):
        objects = []
        now = timezone.now()
        product = Product.objects.get(id=2)
        sub_product = SubProduct.objects.get(id=6)
        process = ProductProcess.objects.get(pk='cfc2113a-d95a-4de3-a89a-13c667942c93')
        place = Place.objects.get(id=28)

        for sito, text, _, full_sn in self.DATA:
            objects.append(ProductObject(
                full_sn=full_sn,
                sito_basic_unnamed_place=sito,
                free_plain_text=text,
                product=product,
                sub_product=sub_product,
                last_move=now,
                current_process=process,
                current_place=place,
                sito_cycle_limit=200_000,
            ))
        with transaction.atomic():
            ProductObject.objects.bulk_create(objects, ignore_conflicts=False, batch_size=1000, return_ids=True)
        
        logs = []
        for obj in objects:
            logs.append(ProductObjectProcessLog(
                product_object=obj,
                process=process,
                entry_time=now,
                who_entry="11111",
                place=place
            ))

        ProductObjectProcessLog.objects.bulk_create(logs)

        return Response({
            "inserted": len(objects),
            "status": "done (ONE-TIME IMPORT)"
        })