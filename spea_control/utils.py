from .models import MoveLogSpea



def create_log_to_spea(card, movement_type):
    log = MoveLogSpea.objects.create(
        card=card,
        movement_type=movement_type
    )

    return log