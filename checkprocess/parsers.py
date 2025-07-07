import re
from datetime import datetime


class BaseSNParser:
    def parse(self, full_sn: str):
        raise NotImplementedError("Każdy parser musi mieć metodę `parse()`")


class DefaultSNParser(BaseSNParser):
    def parse(self, full_sn: str):
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

        return serial_number, production_date, expire_date, serial_type, q_code


def get_parser(parser_type: str):
    if parser_type == 'default':
        return DefaultSNParser()
    # elif parser_type == 'datamatrix':
    #     return DataMatrixParser()
    raise ValueError(f"Nieobsługiwany typ parsera: '{parser_type}'")