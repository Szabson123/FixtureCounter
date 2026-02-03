from .models import ProductObject
from django.db.models import Count, Case, When, Value, DateField, F

from django.utils.timezone import now
from datetime import timedelta

from django.conf import settings
from rest_framework.exceptions import ValidationError
from .models import OneToOneMap
import pyodbc

import requests
from requests.exceptions import RequestException
from .custom_validators import ValidationErrorWithCode


def get_printer_info_from_card(production_card):
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={settings.EXTERNAL_SQL_SERVER};"
        f"DATABASE={settings.EXTERNAL_SQL_DB};"
        f"UID={settings.EXTERNAL_SQL_USER};"
        f"PWD={settings.EXTERNAL_SQL_PASSWORD}"
    )

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT TOP 1 *
            FROM printers
            WHERE name IN (?, ?, ?)
            ORDER BY
                CASE
                    WHEN name = ? THEN 0
                    WHEN name = ? THEN 1
                    ELSE 2
                END
            """,
            (str(production_card), f"{production_card}_str1", f"{production_card}_str2",
            str(production_card), f"{production_card}_str1")
        )
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        # Zmieniamy na ValidationErrorWithCode
        raise ValidationErrorWithCode(
            message=f"Błąd SQL: {str(e)}", 
            code="external_db_error"
        )

    if not result:
        raise ValidationErrorWithCode(
            message=f"Brak danych drukarki dla karty: {production_card}", 
            code="printer_data_not_found"
        )

    printer_name = result[3]   # '15007535'
    raw_model_name = result[4]  # np. 'LF(AIM-H10-SAC305); LF(OM-338-PT)'
    model_names = [x.strip() for x in raw_model_name.split(';') if x.strip()]

    mapped_names = []

    for name in model_names:
        try:
            map_entry = OneToOneMap.objects.get(s_input=name)
            mapped_names.append(map_entry.s_output)
        except OneToOneMap.DoesNotExist:
            raise ValidationErrorWithCode(
                message=f"Brak mapowania dla modelu: {name}", 
                code="mapping_missing"
            )

    return mapped_names, printer_name


def check_fifo_violation(current_object):
    if not current_object.current_process:
        return None

    qs_filters = {
        'current_process': current_object.current_process,
        'current_place__isnull': False,
        'sub_product': current_object.sub_product,
    }

    excluded_ids = [current_object.id]

    if current_object.is_mother:
        excluded_ids += list(current_object.child_object.values_list('id', flat=True))

    children = ProductObject.objects.filter(
        is_mother=False,
        **qs_filters
    ).exclude(id__in=excluded_ids).annotate(
        sort_date=Case(
            When(exp_date_in_process__isnull=False, then=F('exp_date_in_process')),
            When(expire_date__isnull=False, then=F('expire_date')),
            default=Value(now().date() + timedelta(days=365 * 100)),
            output_field=DateField()
        )
    )
    
    empty_mothers = ProductObject.objects.filter(
        is_mother=True,
        **qs_filters
        
    ).exclude(id__in=excluded_ids).annotate(
        children_count=Count('child_object'),
        sort_date=Case(
            When(exp_date_in_process__isnull=False, then=F('exp_date_in_process')),
            When(expire_date__isnull=False, then=F('expire_date')),
            default=Value(now().date() + timedelta(days=365 * 100)),
            output_field=DateField()
        )
    ).filter(children_count=0)

    combined = list(children) + list(empty_mothers)

    current_sort_date = (
        current_object.exp_date_in_process or
        current_object.expire_date or
        now().date() + timedelta(days=365 * 100)
    )
    current_created_at = current_object.created_at

    for obj in combined:
        obj_sort_date = obj.sort_date
        if obj_sort_date < current_sort_date or (
            obj_sort_date == current_sort_date and obj.created_at < current_created_at - timedelta(hours=2)
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


def detect_parser_type(full_sn: str) -> str:
    if not full_sn or not isinstance(full_sn, str):
        return 'undefined'

    full_sn = full_sn.strip()

    if full_sn.startswith('(V)'):
        if 'AIM' in full_sn:
            return 'aim_parser'
        elif 'MACDERMID' in full_sn:
            return 'italgas'
        elif 'heraeus' in full_sn.lower():
            return 'heraus_parser'
        elif 'SE4420' in full_sn:
            return 'klej_parser'

    if '[)>' in full_sn:
        return 'alpha_parser'

    if full_sn.startswith('S') or full_sn.startswith('T') or full_sn.startswith('#') or full_sn.startswith('W'):
        return 'sito_default'

    return 'undefined'

def poke_process(process_id):
    try:
        response = requests.get(f"http://127.0.0.1:8001/micro/new-product-poke/{process_id}/", timeout=30)

        if response.status_code >= 200 and response.status_code < 1000:
            return True
        
        raise ValidationError({"error": "Błąd podczas wykonywania poke – endpoint zwrócił błąd."})

    except requests.exceptions.RequestException as e:
        print("POKE ERROR:", e)
        raise ValidationError({"error": "Nie udało się skontaktować z endpointem poke."})
    
