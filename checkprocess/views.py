
import requests

from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError, models
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import connection
from django.db.models import F, Count, Q, Value, CharField, DateTimeField, TextField, UUIDField
from django.db.models.functions import Coalesce

from rest_framework import viewsets, status, filters, mixins
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, GenericAPIView
from rest_framework.filters import OrderingFilter, SearchFilter

from .filters import ProductObjectFilter, ProductObjectProcessLogFilter
from .parsers import get_parser
from .utils import detect_parser_type, get_printer_info_from_card, poke_process
from .validation import ProcessMovementValidator, ValidationErrorWithCode
from .models import (Product, ProductProcess, ProductObject, ProductObjectProcess, ProductObjectProcessLog, Place, AppToKill, Edge, SubProduct,
                    LastProductOnPlace, PlaceGroupToAppKill, MessageToApp, LogFromMistake)

from .serializers import(ProductSerializer, ProductProcessSerializer, ProductObjectSerializer, ProductObjectProcessSerializer,
                        ProductObjectProcessLogSerializer, PlaceSerializer, EdgeSerializer, BulkProductObjectCreateSerializer, BulkProductObjectCreateToMotherSerializer,
                        PlaceGroupToAppKillSerializer, RetoolingSerializer, StencilStartProdSerializer, LogFromMistakeSerializer, ProductProcessSimpleSerializer,
                        AppToKillSerializer, PlaceSerializerAdmin, UnifyLogsSerializer, ProductObjectAdminSerializer, ProductObjectAdminSerializerProcessHelper)

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


class ProductProcessList(ListAPIView):
    serializer_class = ProductProcessSimpleSerializer
    queryset = ProductProcess.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['label']


class PlaceViewSet(viewsets.ModelViewSet):
    serializer_class = PlaceSerializer
    
    def get_queryset(self):
        process_id = self.kwargs.get('process_id')
        return Place.objects.filter(process=process_id)
    
    def perform_create(self, serializer):
        process_id = self.kwargs.get('process_id')
        process = get_object_or_404(ProductProcess, pk=process_id)
        serializer.save(process=process)


class PlaceInGroupAdmin(viewsets.ModelViewSet):
    #permission_classes=[AllowAny], 
    serializer_class=PlaceSerializerAdmin
    queryset = Place.objects.all()

    http_method_names = ['get', 'patch']

    def get_queryset(self):
        group_id = self.kwargs.get('group_id')
        return Place.objects.filter(group_id=group_id)


class ProductObjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProductObjectSerializer
    queryset = ProductObject.objects.all()

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
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

    search_fields = ['free_plain_text', 'sito_basic_unnamed_place', 'serial_number', 'full_sn']

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
                
                ProductObjectProcessLog.objects.create(product_object=product_object, process=process, entry_time=timezone.now(), who_entry=who_entry, place=place_obj, movement_type='create')

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
            
            ProductObjectProcessLog.objects.create(product_object=product_object, process=process, who_entry=who, place=place, movement_type=movement_type)
            
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

        validator = ProcessMovementValidator(process_uuid, full_sn, place_name, movement_type, who)

        try:
            validator.run()

            product_object = validator.product_object
            place = validator.place
            process = validator.process

            try:
                defaults = getattr(process, "defaults", None)

                if not defaults or not defaults.stencil_production_process_type:
                    raise ValidationErrorWithCode(
                        message="Ten proces nie pozwala na rozpoczęcie produkcji przez ten endpoint.",
                        code="process_config_error"
                    )
                
                if not defaults.use_poke:
                    raise ValidationErrorWithCode(
                        message="Ten proces wymaga poke do aplikacji.",
                        code="poke_required"
                    )

                if defaults.use_poke:
                    poke_process(7)

                handler = MovementHandler.get_handler(movement_type, product_object, place, process, who)
                handler.execute()

                message_one = 'Produkcja tym sitem trwa ponad 7.5 godziny za 30 min aplikacja zostanie wyłączona'
                message_two = 'Produkcja trwa już 8 godzin wyłączam aplikacje do czasu przezbrojenia'

                MessageToApp.objects.create(
                    line=place,
                    message=message_one,
                    send=False,
                    when_trigger=timezone.now() + timedelta(hours=7, minutes=30),
                    product=product_object.product
                )

                MessageToApp.objects.create(
                    line=place,
                    message=message_two,
                    send=False,
                    when_trigger=timezone.now() + timedelta(hours=8),
                    product=product_object.product
                )

                LastProductOnPlace.objects.create(
                    product_process=process, 
                    place=place
                )
                
                return Response(
                    {"detail": "Ruch został wykonany pomyślnie."},
                    status=status.HTTP_200_OK
                )
            
            except ValidationErrorWithCode as e:
                validator.save_error_log(e)
                raise e

        except ValidationErrorWithCode as e:
            return Response(
                {"detail": e.message, "code": e.code},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            validator.save_error_log(ValidationErrorWithCode(str(e), code="internal_server_error"))
            
            return Response(
                {"detail": "Wystąpił nieoczekiwany błąd serwera.", "code": "unknown_error"},
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
        
        validator = ProcessMovementValidator(process_uuid, full_sn, place_name, movement_type, who)
        try:
            validator.run()

            product_object = validator.product_object
            place = validator.place
            process = validator.process
            
            try:
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
                validator.save_error_log(e)
                raise e
        
        except ValidationErrorWithCode as e:
            return Response(
                {"detail": e.message, "code": e.code},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
             return Response(
                {"detail": str(e), "code": "unknown_error"},
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
        
        if group.checking == False:
            return Response({
                "group": group_name,
                "expired": False,
                "places_with_expired": [],
                "kill": False,
                "per_place": {}
            }, status=200)

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
        manual_kill_any = any(per_place_flags.values()) if per_place_flags else False
        effective_kill = manual_kill_any or expired_any
        
        group.last_check = timezone.now()
        group.save()

        return Response({
            "group": group_name,
            "expired": expired_any,
            "places_with_expired": places_with_expired,
            "kill": effective_kill,
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
                        place=place_obj,
                        movement_type='create'
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
                        place=place_obj,
                        movement_type='create'
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
        

class LogFromMistakeData(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = LogFromMistakeSerializer
    queryset = LogFromMistake.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['process__label', 'place__name']
    search_fields = []
    ordering_fields = []


class UnifyLogsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class UnifiedLogsViewSet(viewsets.GenericViewSet):
    serializer_class = UnifyLogsSerializer
    pagination_class = UnifyLogsPagination
    queryset = LogFromMistake.objects.none() 

    def list(self, request, *args, **kwargs):
        process_uuid = self.kwargs.get('process_id')
        place_id = self.kwargs.get('place_id')

        mistakes_qs = LogFromMistake.objects.all()
        process_qs = ProductObjectProcessLog.objects.all()

        if process_uuid:
            mistakes_qs = mistakes_qs.filter(process_id=process_uuid)
            process_qs = process_qs.filter(process_id=process_uuid)

        elif place_id:
            mistakes_qs = mistakes_qs.filter(place_id=place_id)
            process_qs = process_qs.filter(place_id=place_id)

        else:
            return Response({"error": "Missing process_id or place_id"}, status=400)
        
        mistakes_qs = mistakes_qs.annotate(
            log_type=Value('MISTAKE', output_field=CharField()),
            date=F('created_at'),
            who_value=F('who'),
            movement=F('movement_type'),
            proc_label=F('process__label'),
            pl_name=F('place__name'),
            proc_id=F('process_id'),
            pl_id=F('place_id'),
            info=F('error_message'),
        ).values(
            'id', 'log_type', 'date', 'who_value', 'movement',
            'proc_id', 'proc_label', 'pl_id', 'pl_name', 'info'
        )

        process_qs = process_qs.annotate(
            log_type=Value('PROCESS', output_field=CharField()),
            date=F('entry_time'),
            who_value=F('who_entry'),
            movement=F('movement_type'),
            proc_label=F('process__label'),
            pl_name=F('place__name'),
            proc_id=F('process_id'),
            pl_id=F('place_id'),
            info=Value(None, output_field=TextField()),
        ).values(
            'id', 'log_type', 'date', 'who_value', 'movement',
            'proc_id', 'proc_label', 'pl_id', 'pl_name', 'info'
        )

        union_qs = mistakes_qs.union(process_qs, all=True)
        union_qs = union_qs.order_by('-date')

        page = self.paginate_queryset(union_qs)
        if page is not None:
            mapped_data = [
                {
                    'id': item['id'],
                    'log_type': item['log_type'],
                    'date': item['date'],
                    'who': item['who_value'],
                    'movement_type': item['movement'],
                    'error_message': item['info'],
                    'process_id': item['proc_id'],
                    'process_label': item['proc_label'],
                    'place_id': item['pl_id'],
                    'place_name': item['pl_name'],
                }
                for item in page
            ]

            serializer = self.get_serializer(mapped_data, many=True)
            return self.get_paginated_response(serializer.data)

        return Response(serializer.data)
    

class ProductObjectAdminViewSet(viewsets.ModelViewSet):
    serializer_class = ProductObjectAdminSerializer
    queryset = ProductObject.objects.all()
    pagination_class = UnifyLogsPagination

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        objects = (
            ProductObject.objects
            .select_related('product', 'current_process', 'current_place', 'sub_product')
            .filter(product=product_id)
            .order_by(F('last_move').desc(nulls_last=True)) #Tylko dla postgresql
        )
        return objects


class ProductObjectAdminViewSetProcessHelper(ListAPIView):
    serializer_class = ProductObjectAdminSerializerProcessHelper
    pagination_class = UnifyLogsPagination
    queryset = ProductProcess.objects.none()

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductProcess.objects.filter(product_id=product_id)
    

class ProductObjectAdminViewSetPlaceHelper(ListAPIView):
    serializer_class = ProductObjectAdminSerializerProcessHelper
    pagination_class = UnifyLogsPagination
    queryset = Place.objects.none()

    def get_queryset(self):
        process_id = self.kwargs.get('process_id')
        return Place.objects.filter(process=process_id)
