import re
from datetime import datetime
from typing import Optional, Tuple


def parse_full_sn(full_sn: str) -> Tuple[str, Optional[datetime], Optional[datetime]]:
    """
    Parsuje full_sn i zwraca: serial_number, production_date, expire_date
    """
    if not full_sn:
        raise ValueError("Brak pełnego numeru seryjnego (full_sn).")

    try:
        serial_match = re.search(r'3SS(\d+)', full_sn)
        prod_date_match = re.search(r'6D(\d{8})', full_sn)
        exp_date_match = re.search(r'14D(\d{8})', full_sn)

        serial_number = serial_match.group(1)
        production_date = (
            datetime.strptime(prod_date_match.group(1), "%Y%m%d").date()
            if prod_date_match else None
        )
        expire_date = (
            datetime.strptime(exp_date_match.group(1), "%Y%m%d").date()
            if exp_date_match else None
        )

        return serial_number, production_date, expire_date

    except Exception as e:
        raise ValueError(f"Nie udało się sparsować full_sn: {e}")
