from .models import ProductObject, ProductProcess, AppToKill, ProductObjectProcessLog, ProductObjectProcess, BackMapProcess
from django.shortcuts import get_list_or_404


def can_return_from_to(current_process: ProductProcess, target_process: ProductProcess) -> bool:
    if not current_process or not target_process:
        return False
    return BackMapProcess.objects.filter(front=current_process, back=target_process).exists()


class ValidationErrorWithCode(Exception):
    def __init__(self, message, code=None):
        self.message = message
        self.code = code
        super().__init__(message)


class ProcessEntryValidator:
    def __init__(self, full_sn: str, process_id: int, place_name: str):
        self.full_sn = full_sn
        self.process_id = process_id
        self.place_name = place_name

        self.obj: ProductObject = None
        self.process: ProductProcess = None
        self.previous_process: ProductProcess = None
        self.target_po_proc: ProductObjectProcess = None

    def run(self):
        self._load_process()
        self._set_killing_flag(True)
        self._load_object()
        self._validate_previous_process()
        self._check_target_process_assigned()
        self.check_if_can_return_or_raise()
        return self.obj, self.process, self.target_po_proc

    def _load_process(self):
        try:
            self.process = ProductProcess.objects.get(id=self.process_id)
        except ProductProcess.DoesNotExist:
            raise ValidationErrorWithCode("Proces nie istnieje.")

    def _load_object(self):
        try:
            self.obj = ProductObject.objects.get(full_sn=self.full_sn)
        except ProductObject.DoesNotExist:
            raise ValidationErrorWithCode("Obiekt o podanym numerze SN nie istnieje.")

        if self.obj.end:
            raise ValidationErrorWithCode(
                "Obiekt zakończył już swój cykl życia i nie może być modyfikowany.",
                code="object_ended"
            )

        if self.process.product_id != self.obj.product_id:
            raise ValidationErrorWithCode("Proces nie należy do tego samego produktu.")

        if self.obj.current_process_id == self.process_id:
            raise ValidationErrorWithCode("Obiekt już znajduje się w tym procesie.")

        self.previous_process = ProductProcess.objects.filter(
            product=self.obj.product,
            order=self.process.order - 1
        ).first()

        if self.process.ending_process:
            self.obj.end = True
            self.obj.save(update_fields=["end"])
            
    def _validate_previous_process(self):
        if self.process.ending_process:
            return

        if not self._previous_process_is_completed():
            raise ValidationErrorWithCode("Poprzedni proces nie został zakończony poprawnie.", code="previous_incomplete")

    def _check_target_process_assigned(self):
        self.target_po_proc = self.obj.assigned_processes.filter(process=self.process).first()
        if not self.target_po_proc:
            raise ValidationErrorWithCode("Brak przypisania procesu do obiektu.", code="not_assigned")

    def _previous_process_is_completed(self):
        if not self.previous_process:
            return False

        previous_proc_instance = self.obj.assigned_processes.filter(process=self.previous_process).first()
        if not previous_proc_instance:
            return False

        last_log = ProductObjectProcessLog.objects.filter(
            product_object_process=previous_proc_instance
        ).order_by("-entry_time").first()

        if not last_log:
            return False

        has_entry_and_exit = last_log.entry_time and last_log.exit_time
        return has_entry_and_exit

    def _set_killing_flag(self, value: bool = True):
        if self.process.killing_app:
            AppToKill.objects.filter(line_name__name=self.place_name).update(killing_flag=value)
        print(f"USTAWIAM KILL FLAG = {value} dla miejsca: {self.place_name}")
            
    def check_if_can_return_or_raise(self):
        if not self.target_po_proc.logs.exists():
            return

        current_process = self.obj.current_process

        if not current_process:
            raise ValidationErrorWithCode(
                "Obiekt został już odebrany w tym procesie lub cofnięcie nie jest dozwolone.",
                code="already_received"
            )

        if current_process.order < self.process.order:
            open_logs = self.target_po_proc.logs.filter(exit_time__isnull=True).exists()
            if open_logs:
                raise ValidationErrorWithCode(
                    "Obiekt już ma otwarty log w tym procesie.",
                    code="open_log_exists"
                )
            return 

        allowed_back = can_return_from_to(current_process, self.process)
        if not allowed_back:
            raise ValidationErrorWithCode(
                "Cofnięcie nie jest dozwolone.",
                code="not_in_back_map"
            )

        current_proc_instance = self.obj.assigned_processes.filter(process=current_process).first()
        not_completed = current_proc_instance
        no_place = self.obj.current_place is None

        if not_completed and no_place:
            return

        raise ValidationErrorWithCode(
            "Nie spełniono warunków cofnięcia procesu.",
            code="invalid_return_conditions",
        )
