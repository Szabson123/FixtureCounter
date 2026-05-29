from rest_framework.serializers import ValidationError


def validate_unique_values(value):
    if len(value) != len(set(value)):
        raise ValidationError("Elementy na liście muszą być unikalne")
    return value