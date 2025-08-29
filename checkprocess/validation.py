from .models import ProductObject, ProductProcess, AppToKill, ProductObjectProcessLog, ProductObjectProcess, Edge, Place, ProductProcessCondition, ConditionLog
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

        if self.movement_type == 'receive' or self.movement_type == 'check':
            self.resolve_target_process()
            self.validate_process_receive_with_current_place()
            self.set_killing_flag_on_true_if_need()
            if self.check_current_process_condition():
                self.check_cond_path()

            self.validate_object_existence_and_status()
            self.validate_product_not_already_in_process()
            
            if not self.check_current_process_condition():
                self.validate_receive_without_move()
                
            if self.movement_type == 'receive':
                self.validate_only_one_place()

            self.validate_edge_can_move()
            self.validate_settings_in_process()
            

        elif self.movement_type == 'move':
            self.validate_object_existence_and_status()
            self.validate_process_and_current_process()
            self.validate_settings_in_process()
            self.validate_no_current_place_in_move()
            self.validate_fifo_rules()
            self.validate_object_quranteen_time()
            
        elif self.movement_type == 'trash':
            self.validate_process_receive_with_current_place()
            self.validate_object_existence_and_status()
            self.validate_is_trash_process()
        
    
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
        for attr in ['defaults','starts','conditions','endings']:
            try:
                if getattr(self.process, attr):
                    return
            except ObjectDoesNotExist:
                pass
        raise ValidationErrorWithCode('Proces nie ma zdefiniowanych żadnych ustawień.', 'no_process_settings')
        
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
        if self.movement_type not in ['move', 'receive', 'trash', 'check']:
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
            raise ValidationErrorWithCode('Docelowy proces nie istnieje.','target_process_not_found')

        src = self.product_object.current_process
        has_edge = Edge.objects.filter(source=src, target=target_process).exists()
        if not has_edge:
            src_label = src.label if src else '(brak bieżącego procesu)'
            raise ValidationErrorWithCode(
                message=f'Brak przejścia z procesu "{src_label}" do "{target_process.label}".',
                code='edge_not_defined'
            )
        self.process = target_process
            
    def validate_fifo_rules(self):
        if self.process.respect_fifo_rules:
            result = check_fifo_violation(self.product_object)
            if result:
                raise ValidationErrorWithCode(
                    message=result["error"],
                    code="fifo_violation"
                )
        else:
            return
            
    def validate_only_one_place(self):
        try:
            place = Place.objects.get(name=self.place_name, process=self.process)
        except:
            raise ValidationErrorWithCode(
                message='Podane miejsce nie istnieje',
                code='place_not_found'
            )
        if place.only_one_product_object:
            if ProductObject.objects.filter(current_place=place, end=False).exists():
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
        if self.movement_type != 'check':
            try:
                self.place = Place.objects.get(name=self.place_name, process=self.process)
            except Place.DoesNotExist:
                raise ValidationErrorWithCode(
                    message='Podane miejsce nie istnieje lub nie należy do wskazanego procesu.',
                    code='place_not_found'
                )
    
    def set_killing_flag_on_true_if_need(self):
        if not self.process or not self.process.killing_app:
            return
        
        if not self.place:
            return
        
        try:
            kill_flag = AppToKill.objects.get(line_name=self.place)
        except AppToKill.DoesNotExist:
            raise ValidationErrorWithCode(
                message='AppKill nie istnieje',
                code='app_kill_no_exist'
            )

        kill_flag.killing_flag = True
        kill_flag.save()
    
    def validate_is_trash_process(self):
        if not hasattr(self.process, 'endings'):
            raise ValidationErrorWithCode(
                message='Ten proces nie jest oznaczony jako trash (brakuje ustawień zakończenia).',
                code='not_a_trash_process'
            )
        
    def check_current_process_condition(self):
        src = getattr(self.product_object, 'current_process', None)
        if not src:
            return False
        
        if not Edge.objects.filter(source=src, target=self.process).exists():
            return False
        
        return ProductProcessCondition.objects.filter(product_process=src).exists()
    
    def check_cond_path(self):
        if self.process.cond_path is None:
            raise ValidationErrorWithCode(
                message="Poprzednia faza jest warunkowa, ale w docelowej nie skonfigurowano drogi True/False.",
                code="no_settings_phase"
            )
        src = self.product_object.current_process
        cond_log = (ConditionLog.objects.filter(process=src, product=self.product_object).order_by('-time_date').first())
        if not cond_log:
            raise ValidationErrorWithCode(
                message="Brak logu z fazy warunkowej — nie można przyjąć obiektu do nowego procesu.",
                code='log_not_exist'
            )

        if cond_log.result != self.process.cond_path:
            raise ValidationErrorWithCode(
                message="Próbujesz przenieść obiekt niezgodnie z wynikiem poprzedniej fazy.",
                code="wrong_condition"
            )