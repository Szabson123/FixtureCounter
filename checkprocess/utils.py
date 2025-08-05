from .models import ProductObject
from django.db.models import Count, Case, When, Value, DateField, F

from django.utils.timezone import now
from datetime import timedelta

from django.conf import settings
from rest_framework.exceptions import ValidationError
from .models import OneToOneMap
import pyodbc


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
        cursor.execute("SELECT * FROM printers WHERE name = ?", production_card)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
    except Exception as e:
        raise ValidationError(f"Błąd podczas łączenia z bazą zewnętrzną: {str(e)}")

    if not result:
        raise ValidationError(f"Brak danych drukarki dla production_card: {production_card}")

    printer_name = result[3]   # '15007535'
    raw_model_name = result[4] # 'LF(OM-338-PT)'

    try:
        map_entry = OneToOneMap.objects.get(s_input=raw_model_name)
        normalized_name = map_entry.s_output
    except OneToOneMap.DoesNotExist:
        raise ValidationError(f"Nie znaleziono mapowania dla modelu: {raw_model_name}")

    return normalized_name


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
         # Tutaj w przyszłości wiecej if jesli będizemy mieli typy
        return 'aim_parser'

    if '[)>' in full_sn:
        return 'alpha_parser'

    if full_sn.startswith('TX'):
        return 'tecnolab_parser'

    return 'undefined'