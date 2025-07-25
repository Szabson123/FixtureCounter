from .models import ProductObject, ProductProcess, AppToKill, ProductObjectProcessLog, ProductObjectProcess, Edge, Place
from django.shortcuts import get_list_or_404
from django.core.exceptions import ObjectDoesNotExist
from .utils import check_fifo_violation
from django.utils.timezone import now


class ValidationErrorWithCode(Exception):
    def __init__(self, message, code=None):
        self.message = message
        self.code = code
        super().__init__(message)


class ProcessMovementValidator:
    def __init__(self, process_uuid, full_sn, place_name, movement_type):
        self.process_uuid = process_uuid
        self.full_sn = full_sn
        self.place_name = place_name
        self.movement_type = movement_type
        
        self.product_object = None
        self.process = None
        self.place = None
        
    def run(self):
        self.validate_exists_and_not_end()
        self.validate_movement_type()
        
        if self.movement_type == 'receive':
            self.resolve_target_process()
            self.validate_product_not_already_in_process()
            self.validate_receive_without_move()
            self.validate_edge_can_move()
            self.validate_settings_in_process()
            self.validate_only_one_place()
            self.validate_process_receive_with_current_place()
            self.set_killing_flag_on_true_if_need()
            
        elif self.movement_type == 'move':
            self.validate_process_and_current_process()
            self.validate_settings_in_process()
            self.validate_fifo_rules()
            # self.validate_process_receive_with_current_place()
            self.validate_object_quranteen_time()
    
    
    def validate_receive_without_move(self):
        if self.product_object.current_place:
            raise ValidationErrorWithCode(
                message="Nie możesz przyjąć tego produktu bo nie wyciągnąłeś go z poprzedniego procesu",
                code="receive_without_move"
            )
            
    def validate_settings_in_process(self):
        settings_attrs = ['default', 'starts', 'condition', 'ending']
        for attr in settings_attrs:
            if hasattr(self.process, attr):
                return 
            
        raise ValidationErrorWithCode(
            message='Proces nie ma zdefiniowanych żadnych ustawień.',
            code='no_process_settings'
        )
        
    def resolve_target_process(self):
        try:
            self.process = ProductProcess.objects.get(id=self.process_uuid)
        except ProductProcess.DoesNotExist:
            raise ValidationErrorWithCode(
                message='Proces docelowy nie istnieje.',
                code='target_process_not_found'
            )
    
    def validate_product_not_already_in_process(self):
        current_process = self.product_object.current_process

        if current_process and str(current_process.id) == str(self.process.id):
            raise ValidationErrorWithCode(
                message='Ten produkt już znajduje się w tym procesie.',
                code='already_in_process'
            )
    
    def validate_exists_and_not_end(self):
        try:
            self.product_object = ProductObject.objects.get(full_sn=self.full_sn)
        except ObjectDoesNotExist:
            raise ValidationErrorWithCode(
                message=f'Taki objekt nie istnieje {self.full_sn}',
                code = 'object_does_not_exist'
            )
        
        if self.product_object.end:
            raise ValidationErrorWithCode(
                message=f'Obiekt Został oznaczony jako skończony {self.full_sn}',
                code = 'object_already_ended'
            )
            
    def validate_movement_type(self):
        if self.movement_type not in ['move', 'receive']:
            raise ValidationErrorWithCode(
                message=f'Typ ruchu "{self.movement_type}" nie jest obsługiwany.',
                code='movement_type_does_not_exist'
            )
            
    def validate_process_and_current_process(self):
        current_process = self.product_object.current_process
        
        if not current_process or str(current_process.id) != str(self.process_uuid):
            raise ValidationErrorWithCode(
                message='Ten produkt nie należy do tego procesu i nie możesz go przenieść.',
                code='process_mismatch'
            )
        
        self.process = current_process
    
    def validate_edge_can_move(self):
        try:
            target_process = ProductProcess.objects.get(id=self.process_uuid)
        except ProductProcess.DoesNotExist:
            raise ValidationErrorWithCode(
                message='Docelowy proces nie istnieje.',
                code='target_process_not_found'
            )
        
        has_edge = Edge.objects.filter(source=self.product_object.current_process, target=target_process).exists()
        
        if not has_edge:
            raise ValidationErrorWithCode(
                message=f'Brak przejścia z procesu "{self.product_object.current_process.label}" do "{target_process.label}".',
                code='edge_not_defined'
            )
        self.process = target_process
            
    def validate_fifo_rules(self):
        result = check_fifo_violation(self.product_object)
        if result:
            raise ValidationErrorWithCode(
                message=result["error"],
                code="fifo_violation"
            )
            
    def validate_only_one_place(self):
        try:
            place = Place.objects.get(name=self.place_name, process=self.process)
        except:
            raise ValidationErrorWithCode(
                message='Podane miejsce nie istnieje',
                code='place_not_found'
            )
        if place.only_one_product_object:
            exist = ProductObject.objects.filter(current_place=place)
            if exist:
                raise ValidationErrorWithCode(
                message='To miejsce jest oznaczone jako jeden produkt jedno miejsce a w nim już coś się znajduje',
                code='busy_place'
            )
                
    def validate_object_quranteen_time(self):
        if self.product_object.quranteen_time:
            if now() < self.product_object.quranteen_time:
                raise ValidationErrorWithCode(
                    message="Obiekt znajduje się w kwarantannie i nie może być jeszcze przeniesiony.",
                    code="quarantine_active"
                )
            
    def validate_process_receive_with_current_place(self):
        if not self.process:
            try:
                self.process = ProductProcess.objects.get(id=self.process_uuid)
            except ProductProcess.DoesNotExist:
                raise ValidationErrorWithCode(
                    message='Proces nie istnieje.',
                    code='process_not_found'
                )
        
        try:
            self.place = Place.objects.get(name=self.place_name, process=self.process)
        except Place.DoesNotExist:
            raise ValidationErrorWithCode(
                message='Podane miejsce nie istnieje lub nie należy do wskazanego procesu.',
                code='place_not_found'
            )
            
    def _process_has_killing_app(self):
        for attr in ['defaults', 'starts']:
            queryset = getattr(self.process, attr).all()
            if queryset.filter(killing_app=True).exists():
                return True
        return False
    
    def set_killing_flag_on_true_if_need(self):
        if not self._process_has_killing_app():
            return

        kill_flag = AppToKill.objects.filter(line_name=self.place).first()
        if not kill_flag:
            raise ValidationErrorWithCode(
                message='AppKill nie istnieje',
                code='app_kill_no_exist'
            )

        kill_flag.killing_flag = True
        kill_flag.save()
