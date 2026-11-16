from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from checkprocess.models import ProductObject


class Command(BaseCommand):
    help = (
        "Naprawia 'wiszące' kartony: odpina od kartonów zakończone (end=True) dzieci "
        "i zamyka kartony, w których nie zostało żadne aktywne dziecko. "
        "Domyślnie tylko pokazuje, co by zrobił — użyj --apply, żeby zapisać zmiany."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Zapisz zmiany w bazie.')

    def handle(self, *args, apply=False, **options):
        ended_children = ProductObject.objects.filter(
            mother_object__isnull=False, end=True, mother_object__end=False
        ).select_related('mother_object')

        hanging_mothers = ProductObject.objects.filter(is_mother=True, end=False).annotate(
            all_children=Count('child_object'),
            active_children=Count('child_object', filter=Q(child_object__end=False)),
        ).filter(all_children__gt=0, active_children=0)

        self.stdout.write(f"Zakończone dzieci wciąż w kartonach: {ended_children.count()}")
        self.stdout.write(f"Kartony bez aktywnych dzieci do zamknięcia: {hanging_mothers.count()}")
        for m in hanging_mothers:
            self.stdout.write(f"  - {m.full_sn} (id={m.id}, proces={m.current_process_id}, miejsce={m.current_place_id})")

        if not apply:
            self.stdout.write(self.style.WARNING("Tryb podglądu — nic nie zapisano. Uruchom z --apply."))
            return

        with transaction.atomic():
            mother_ids = list(hanging_mothers.values_list('id', flat=True))

            for child in ended_children:
                child.ex_mother = child.mother_object.full_sn
                child.mother_object = None
                child.save(update_fields=['ex_mother', 'mother_object'])

            closed = ProductObject.objects.filter(id__in=mother_ids).update(
                end=True, current_place=None, current_process=None
            )

        self.stdout.write(self.style.SUCCESS(f"Gotowe. Zamknięto kartonów: {closed}"))
