import re
from datetime import datetime
from rest_framework.exceptions import ValidationError

class BaseSNParser:
    def parse(self, full_sn: str):
        raise NotImplementedError("Każdy parser musi mieć metodę `parse()`")


class AlphaSNParser(BaseSNParser):
    def parse(self, full_sn: str):
        sub_product = 'Alpha'
        serial_match = re.search(r'3S([A-Z])(\d+)', full_sn)
        prod_date_match = re.search(r'6D(\d{8})', full_sn)
        exp_date_match = re.search(r'14D(\d{8})', full_sn)
        q_match = re.search(r'@Q(\d+)', full_sn)

        if not serial_match:
            raise ValueError("Brak numeru seryjnego z prefiksem 3S.")

        serial_type = serial_match.group(1)
        serial_number = serial_match.group(2)

        production_date = (
            datetime.strptime(prod_date_match.group(1), "%Y%m%d").date()
            if prod_date_match else None
        )
        expire_date = (
            datetime.strptime(exp_date_match.group(1), "%Y%m%d").date()
            if exp_date_match else None
        )
        q_code = q_match.group(1) if q_match else None

        return sub_product, serial_number, production_date, expire_date, serial_type, q_code
    

class AimSnParser(BaseSNParser):
    def parse(self, full_sn: str):
        sub_product = 'AIM'
        sn_match = re.search(r'\(S\)([^\(]+)', full_sn)
        if not sn_match:
            raise ValueError("Brak numeru seryjnego (S).")
        serial_number = sn_match.group(1)

        prod_date_match = re.search(r'\(D\)(\d{8})', full_sn)
        production_date = (
            datetime.strptime(prod_date_match.group(1), "%Y%m%d").date()
            if prod_date_match else None
        )

        exp_date_match = re.search(r'\(E\)(\d{8})', full_sn)
        expire_date = (
            datetime.strptime(exp_date_match.group(1), "%Y%m%d").date()
            if exp_date_match else None
        )

        return sub_product, serial_number, production_date, expire_date, None, None


class TecnoLabSNParser(BaseSNParser):
    def parse(self, full_sn: str):
        sub_product = 'Tecno lab'
        match = re.search(r'(TX\d{5})', full_sn)
        if not match:
            raise ValueError("Nie znaleziono numeru rozpoczynającego się od TX i 5 cyfr.")
        
        serial_number = match.group(1)

        return sub_product, serial_number, None, None, None, None
    

def get_parser(parser_type: str):
    if parser_type == 'alpha_parser':
        return AlphaSNParser()
    elif parser_type == 'aim_parser':
        return AimSnParser()
    elif parser_type == 'tecnolab_parser':
        return TecnoLabSNParser()
    raise ValidationError(f"Nieobsługiwany typ parsera: '{parser_type}'")


