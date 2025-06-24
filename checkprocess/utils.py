import re
from datetime import datetime
from typing import Optional, Tuple
from .models import ProductObject
from django.db.models import Count, Case, When, Value, DateField, F

from django.utils.timezone import now
from datetime import timedelta
from django.db import models

def parse_full_sn(full_sn: str) -> Tuple[str, Optional[datetime], Optional[datetime], str, Optional[str]]:
    
    if not full_sn:
        raise ValueError("Brak pełnego numeru seryjnego (full_sn).")

    try:
        serial_match = re.search(r'3S([A-Z]{1})(\d+)', full_sn)
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

    except Exception as e:
        raise ValueError(f"Nie udało się sparsować full_sn: {e}")


def check_fifo_violation(current_object):
    if not current_object.current_process:
        return None

    children = ProductObject.objects.filter(
        current_process=current_object.current_process,
        current_place__isnull=False,
        is_mother=False
    ).exclude(id=current_object.id).annotate(
        sort_date=Case(
            When(exp_date_in_process__isnull=False, then=F('exp_date_in_process')),
            When(expire_date__isnull=False, then=F('expire_date')),
            default=Value(now().date() + timedelta(days=365 * 100)),
            output_field=DateField()
        )
    )

    empty_mothers = ProductObject.objects.filter(
        current_process=current_object.current_process,
        current_place__isnull=False,
        is_mother=True
    ).exclude(id=current_object.id).annotate(
        children_count=Count('child_object'),
        sort_date=Case(
            When(exp_date_in_process__isnull=False, then=F('exp_date_in_process')),
            When(expire_date__isnull=False, then=F('expire_date')),
            default=Value(now().date() + timedelta(days=365 * 100)),
            output_field=DateField()
        )
    ).filter(children_count=0)

    combined = list(children) + list(empty_mothers)
    combined.sort(key=lambda x: (x.sort_date, x.created_at))

    sort_date_current = (
        current_object.exp_date_in_process or current_object.expire_date or (now().date() + timedelta(days=365 * 100))
    )

    for obj in combined:
        sort_date_obj = (
            obj.exp_date_in_process or obj.expire_date or (now().date() + timedelta(days=365 * 100))
        )

        if sort_date_obj < sort_date_current or (
            sort_date_obj == sort_date_current and obj.created_at < current_object.created_at
        ):
            return {
                "error": (
                    f"W tym procesie znajduje się produkt, który powinien być wybrany jako pierwszy: "
                    f"serial: {obj.serial_number}, miejsce: {obj.current_place.name if obj.current_place else 'Brak'}"
                ),
                "place": obj.current_place.name if obj.current_place else "Brak",
                "serial_number": obj.serial_number
            }

    return None