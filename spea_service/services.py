from .utils import polmesprod_database_string as conn_str
import pyodbc
from pyodbc import connect
from .models import EndedCodesWithQueue
from goldensample.models import MasterSample
from rest_framework.serializers import ValidationError
from django.db import transaction

# Not use right now after refactor
def get_end_code_of_sn(cursor, phase_id, sn):
    query = """SELECT TOP (1) [IDMeasure] FROM [Measure].[dbo].[HeaderDataLog] WHERE IdPhase = ? AND MSN = ?
               ORDER BY TestDateTime DESC"""
    cursor.execute(query, (phase_id, sn))
    return cursor.fetchall()
    

class SetGoodOrderService:
    def __init__(self, full_model, goldens, machine_name, phase_id):
        self.full_model = full_model
        self.goldens = goldens
        self.machine_name = machine_name
        self.phase_id = phase_id

    @transaction.atomic
    def prepare_end_codes_in_queue(self):
        for index, sn in enumerate(self.goldens, start=1):
            # In this place we know they exists
            code_value = MasterSample.objects.filter(sn=sn).values_list('endcodes__code', flat=True).first()
            if code_value:
                EndedCodesWithQueue.objects.create(
                    full_validation=self.full_model,
                    code=code_value,
                    queue=index
                )
            else:
                raise ValueError({"error": f"{sn} -> golden dont have endcode"})
