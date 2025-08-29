from checkprocess.validation import ValidationErrorWithCode
from checkprocess.models import ProductObjectProcessLog, AppToKill, ConditionLog
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.db import transaction
from django.utils import timezone


class MovementHandler:
    @staticmethod
    def get_handler(movement_type, product_object, place, process, who, result=None):
        if movement_type == 'move':
            return MoveHandler(product_object, place, process, who)
        elif movement_type == 'receive':
            return ReceiveHandler(product_object, place, process, who)
        elif movement_type == 'check':
            return CheckHandler(product_object, place, process, who, result)
        else:
            raise ValidationErrorWithCode(
                message='Brak obsługi dla tego typu ruchu',
                code='unsuported_movement_type'
            )
        

class BaseMovementHandler:
    def __init__(self, product_object, place, process, who, result=None):
        self.product_object = product_object
        self.place = place
        self.process = process
        self.who = who
        self.result = result
    
    def execute(self):
        raise NotImplementedError
    
    def _handle_orphaning(self, product_obj):
        mother = product_obj.mother_object

        # Jeśli to nie dziecko lub matka jest też przenoszona razem z nim — nie ruszamy
        if not mother:
            return

        if mother == self.product_object:
            # Matka też bierze udział w operacji – nie odłączamy dziecka
            return

        # Jeśli dziecko jest przenoszone samodzielnie → odłączamy
        product_obj.ex_mother = mother.full_sn
        product_obj.mother_object = None
        product_obj.save()

        # Sprawdzamy, czy matce zostały dzieci
        if not mother.child_object.exists():
            mother.end = True
            mother.current_place = None
            mother.current_process = None
            mother.save()
    

class MoveHandler(BaseMovementHandler):
    @transaction.atomic
    def execute(self):
        self._move_product_object(self.product_object)

        for child in self.product_object.child_object.all():
            self._move_product_object(child)

    def _move_product_object(self, product_object):
        self.delete_current_place(product_object)
        self.set_quarantin_if_needed(product_object)
        self.set_expire_if_needed(product_object)
        self.create_move_log(product_object)
        self._handle_orphaning(product_object)

    def create_move_log(self, product_object):
        log = ProductObjectProcessLog.objects.filter(
            product_object=product_object,
            process=self.process,
            exit_time__isnull=True,
        ).order_by('-entry_time').first()

        if not log:
            raise ValidationErrorWithCode(
                message=f'Taki log nie istnieje dla obiektu {product_object}, co oznacza że produkt nie powinien być w tym procesie',
                code='log_no_exist'
            )
        log.exit_time = datetime.now()
        log.who_exit = self.who
        log.save()

    def delete_current_place(self, product_object):
        product_object.current_place = None
        product_object.save()

    def set_quarantin_if_needed(self, product_object):
        for attr in ['defaults', 'starts', 'conditions']:
            conf = getattr(self.process, attr, None)
            if conf and conf.quranteen_time:
                product_object.quranteen_time = now() + timedelta(hours=conf.quranteen_time)
                product_object.save()
                return

    def set_expire_if_needed(self, product_object):
        for attr in ['defaults', 'starts', 'conditions']:
            conf = getattr(self.process, attr, None)
            if conf and conf.how_much_days_exp_date:
                product_object.exp_date_in_process = now().date() + timedelta(days=conf.how_much_days_exp_date)
                product_object.save()
                return
            

class ReceiveHandler(BaseMovementHandler):
    @transaction.atomic
    def execute(self):
        # Matka
        self._receive_product_object(self.product_object)

        # Dzieci
        for child in self.product_object.child_object.all():
            self._receive_product_object(child)

        self.set_killing_flag_on_false_if_need()

    def _receive_product_object(self, product_obj):
        self.set_current_place_and_process(product_obj)
        self.create_log(product_obj)
        self._handle_orphaning(product_obj)

    def create_log(self, product_obj):
        ProductObjectProcessLog.objects.create(
            product_object=product_obj,
            process=self.process,
            entry_time=timezone.now(),
            who_entry=self.who,
            place=self.place
        )

    def set_current_place_and_process(self, product_obj):
        product_obj.current_place = self.place
        product_obj.current_process = self.process
        product_obj.save()

    def set_killing_flag_on_false_if_need(self):
        if not self.process or not self.process.killing_app:
            return

        try:
            kill_flag = AppToKill.objects.get(line_name=self.place)
        except AppToKill.DoesNotExist:
            raise ValidationErrorWithCode(
                message='AppKill nie istnieje dla danego miejsca.',
                code='app_kill_no_exist'
            )

        if kill_flag.killing_flag:
            kill_flag.killing_flag = False
            kill_flag.save()


class CheckHandler(BaseMovementHandler):
    @transaction.atomic
    def execute(self):
        self.create_log()
        self.set_current_place_and_process()

    def create_log(self):
        ConditionLog.objects.create(process=self.process, product=self.product_object, result=self.result, who=self.who)
        
    def set_current_place_and_process(self):
        product_object = self.product_object
        product_object.current_process = self.process
        product_object.save()
    

