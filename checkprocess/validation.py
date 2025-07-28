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
    def __init__(self, process_uuid, full_sn, place_name, movement_type, who):
        self.process_uuid = process_uuid
        self.full_sn = full_sn
        self.place_name = place_name
        self.movement_type = movement_type
        self.who = who
        
        self.product_object = None
        self.process = None
        self.place = None
        
    def run(self):
        self.try_load_object()
        self.validate_movement_type()
        self.validate_who_make_move()

        if self.movement_type == 'receive':
            self.resolve_target_process()
            self.validate_process_receive_with_current_place()
            self.set_killing_flag_on_true_if_need()
            
            self.validate_object_existence_and_status()
            self.validate_product_not_already_in_process()
            self.validate_receive_without_move()
            self.validate_edge_can_move()
            self.validate_settings_in_process()
            self.validate_only_one_place()

        elif self.movement_type == 'move':
            self.validate_object_existence_and_status()
            self.validate_process_and_current_process()
            self.validate_settings_in_process()
            self.validate_no_current_place_in_move()
            self.validate_fifo_rules()
            self.validate_object_quranteen_time()
    
    def validate_object_existence_and_status(self):
        if not self.product_object:
            raise ValidationErrorWithCode(
                message=f'Taki objekt nie istnieje: {self.full_sn}',
                code='object_does_not_exist'
            )
        if self.product_object.end:
            raise ValidationErrorWithCode(
                message=f'Obiekt został oznaczony jako zakończony: {self.full_sn}',
                code='object_already_ended'
            )
            
    def try_load_object(self):
        try:
            self.product_object = ProductObject.objects.get(full_sn=self.full_sn)
        except ProductObject.DoesNotExist:
            self.product_object = None
            
    def validate_no_current_place_in_move(self):
        if self.product_object.current_place is None:
            raise ValidationErrorWithCode(
                message="Nie możesz ruszyć tego produktu bo nie ma aktualnego miejsca w tym procesie (nigdzie się nie znajduje)",
                code="move_without_place"
            ) 
            
    def validate_who_make_move(self):
        if self.who == None:
            raise ValidationErrorWithCode(
                message="Do wykonania ruchu wymagane jest zeskanowanie fiszki lub podanie numeru identyfikacyjnego",
                code="no_user_loged"
            )
    
    
    def validate_receive_without_move(self):
        if self.product_object.current_place:
            raise ValidationErrorWithCode(
                message="Nie możesz przyjąć tego produktu bo nie wyciągnąłeś go z poprzedniego procesu",
                code="receive_without_move"
            )
            
    def validate_settings_in_process(self):
        settings_attrs = ['defaults', 'starts', 'conditions', 'endings']
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
                message='To miejsce jest oznaczone jako "jeden produkt jedno miejsce" a w nim już coś się znajduje',
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
            conf = getattr(self.process, attr, None)
            if conf and conf.killing_app:
                return True
        return False
    
    def _should_kill_app(self):
        line_empty = not ProductObject.objects.filter(
            current_place=self.place,
            current_process=self.process,
            end=False
        ).exists()
        
        object_bad = (
            self.product_object is None
            or self.product_object.end
            or (
                self.product_object.quranteen_time and
                self.product_object.quranteen_time > now()
            )
        )

        return line_empty and object_bad
    
    def set_killing_flag_on_true_if_need(self):
        if not self._process_has_killing_app():
            return

        if not self.place or not self.process:
            return

        if not self._should_kill_app():
            return

        try:
            kill_flag = AppToKill.objects.get(line_name=self.place, process=self.process)
        except AppToKill.DoesNotExist:
            raise ValidationErrorWithCode(
                message='AppKill nie istnieje',
                code='app_kill_no_exist'
            )

        kill_flag.killing_flag = True
        kill_flag.save()