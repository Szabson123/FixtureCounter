from checkprocess.models import Edge, EdgeOptionsSets, ProductObject, ProductProcess
from checkprocess.validation import ValidationErrorWithCode
from django.db import models

class EdgeSets:
    def __init__(self, process_uuid, full_sn):
        self.edge = None
        self.process_uuid = process_uuid
        self.full_sn = full_sn
        self.edge_settings = None

    def execute(self):
        self.get_edge()
        self._check_edge_settings()
        self.settings_step_by_step()
    
    def get_edge(self):
        try:
            self.edge = Edge.objects.get(source=self.process_uuid)
        except Edge.DoesNotExist:
            try:
                self.edge = Edge.objects.get(target=self.process_uuid)
            except Edge.DoesNotExist:
                raise ValidationErrorWithCode(
                    message='Nie można znaleźć takiej drogi',
                    code='edge_doesnt_exist'
                )
        return self.edge
    
    def _check_edge_settings(self):
        if not self.edge.edgeoptions:
            return
        self.edge_settings = self.edge.edgeoptions

    def settings_step_by_step(self):
        if not self.edge_settings:
            return

        # Pobierz wszystkie pola w EdgeOptionsSets
        for field in EdgeOptionsSets._meta.get_fields():
            if isinstance(field, models.BooleanField):
                field_name = field.name
                value = getattr(self.edge_settings, field_name, False)

                if value:
                    method_name = f"_{field_name}"
                    if hasattr(self, method_name):
                        getattr(self, method_name)()
                    else:
                        continue

    def _set_not_full(self):
        # Na tym etapie wiem że istanieje bo mam validatory przed
        obj = ProductObject.objects.get(full_sn=self.full_sn)
        obj.is_full = False
        obj.save()
    
    def _check_same_out_same_in(self):
        source = self.edge.source

        if ProductObject.objects.filter(current_process=source).exists():
            raise ValidationErrorWithCode(
                message='Inna ilość produktów włożonych do szafy niż wyciągnietych z poprzedniego procesu',
                code='wrong_quantity'
            )


