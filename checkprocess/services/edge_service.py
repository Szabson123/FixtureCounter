from checkprocess.models import Edge, EdgeOptionsSets, ProductObject, ProductProcess
from checkprocess.validation import ValidationErrorWithCode
from django.db import models


class EdgeSameInSameOut:
    def __init__(self, process_uuid, last_sn):
        self.edge = None
        self.edge_settings = None
        self.process_uuid = process_uuid
        self.last_sn = last_sn

    def execute(self):
        self.get_edge()
        self.get_edge_settings()

        if not self.edge_settings or not self.edge_settings.check_same_out_same_in:
            return {
                "info": "Sprawdzanie ilości pominięte (brak ustawień lub flaga wyłączona).",
                "code": "check_same_out_same_in_disabled"
            }
        
        self._check_same_out_same_in()
        return {
            "info": "Sprawdzenie zakończone pomyślnie.",
            "code": "check_same_out_same_in_ok"
        }
    
    def get_edge(self):
        try:
            self.edge = Edge.objects.get(target=self.process_uuid)
        except Edge.DoesNotExist:
            raise ValidationErrorWithCode(
                message='Nie można znaleźć takiej drogi',
                code='edge_doesnt_exist'
            )
        return self.edge

    def get_edge_settings(self):
        try:
            self.edge_settings = self.edge.edgeoptions
        except EdgeOptionsSets.DoesNotExist:
            self.edge_settings = None
        return self.edge_settings

    def _check_same_out_same_in(self):
        source = self.edge.source
        if ProductObject.objects.filter(current_process=source, place=None).exists():
            raise ValidationErrorWithCode(
                message='Inna ilość produktów włożonych do szafy niż wyciągniętych z poprzedniego procesu',
                code='wrong_quantity'
            )


