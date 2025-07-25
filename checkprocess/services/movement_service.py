from checkprocess.validation import ValidationErrorWithCode
from checkprocess.models import ProductObjectProcessLog, AppToKill
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.db import transaction
from django.utils import timezone


class MovementHandler:
    @staticmethod
    def get_handler(movement_type, product_object, place, process, who):
        if movement_type == 'move':
            return MoveHandler(product_object, place, process, who)
        elif movement_type == 'receive':
            return ReceiveHandler(product_object, place, process, who)
        else:
            raise ValidationErrorWithCode(
                message='Brak obsługi dla tego typu ruchu',
                code='unsuported_movement_type'
            )
        

class BaseMovementHandler:
    def __init__(self, product_object, place, process, who):
        self.product_object = product_object
        self.place = place
        self.process = process
        self.who = who
    
    def execute(self):
        raise NotImplementedError
    

class MoveHandler(BaseMovementHandler):
    @transaction.atomic
    def execute(self):
        self.delete_current_place()
        self.set_quarantin_if_needed()
        self.set_expire_if_needed()
        self.create_move_log()
    
    # Log creation
    def create_move_log(self):
        log = ProductObjectProcessLog.objects.filter(
            product_object=self.product_object,
            process=self.process,
            exit_time__isnull=True
        ).order_by('-entry_time').first()

        if not log:
            raise ValidationErrorWithCode(
                message='Taki log nie istnieje, co oznacza że produkt nie powinien być w tym procesie',
                code='log_no_exist'
            )
        log.exit_time = datetime.now()
        log.who_exit = self.who
        
        log.save()
    
    # Delete current Place
    def delete_current_place(self):
        self.product_object.current_place = None
        self.product_object.save()
        
    # if quarantin set quarantin
    
    def set_quarantin_if_needed(self):
        process = self.process
        config_attrs = ['default', 'start', 'condition']

        for attr in config_attrs:
            conf = getattr(process, attr, None)
            if conf and conf.quranteen_time:
                self.product_object.quranteen_time = now() + timedelta(minutes=conf.quranteen_time)
                self.product_object.save()
                return
    
    def set_expire_if_needed(self):
        process = self.process
        config_attrs = ['default', 'start', 'condition']

        for attr in config_attrs:
            conf = getattr(process, attr, None)
            if conf and conf.how_much_days_exp_date:
                self.product_object.exp_date_in_process = now().date() + timedelta(days=conf.how_much_days_exp_date)
                self.product_object.save()
                return
    

class ReceiveHandler(BaseMovementHandler):
    @transaction.atomic
    def execute(self):
        self.set_current_place_and_process()
        self.create_log()
        self.set_killing_flag_on_false_if_need()

    def create_log(self):
        ProductObjectProcessLog.objects.create(product_object=self.product_object, process=self.process, entry_time=timezone.now(), who_entry=self.who, place=self.place)
    
    def set_current_place_and_process(self):
        product_object = self.product_object
        product_object.current_place = self.place
        product_object.current_process = self.process
        product_object.save()
    
    def _process_has_killing_app(self):
        for attr in ['defaults', 'starts']:
            queryset = getattr(self.process, attr).all()
            if queryset.filter(killing_app=True).exists():
                return True
        return False
    
    def set_killing_flag_on_false_if_need(self):
        if not self._process_has_killing_app():
            return

        kill_flag = AppToKill.objects.filter(line_name=self.place).first()
        if not kill_flag:
            raise ValidationErrorWithCode(
                message='AppKill nie istnieje',
                code='app_kill_no_exist'
            )

        kill_flag.killing_flag = False
        kill_flag.save()
    
        

