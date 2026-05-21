from utils import polmesprod_database_string as conn_str
import pyodbc
from pyodbc import connect

def get_end_code_of_sn(cursor, sn):
    
query = 


class SetGoodOrderService:
    def __init__(self, full_model, goldens, machine_name, phase_id):
        self.full_model = full_model
        self.goldens = goldens
        self.machine_name = machine_name
        self.phase_id = phase_id

    def connect_to_polmesprod_database(self):
        with connect(conn_str) as conn:
            cursor = conn.cursor()
