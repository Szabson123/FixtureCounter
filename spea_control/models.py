from django.db import models
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError

import uuid
import os


class LocationSpea(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
    

class SpeaCard(models.Model):
    sn = models.CharField(max_length=255, unique=True)
    location = models.ForeignKey(LocationSpea, null=True, blank=True, default=None, related_name='speacard', on_delete=models.SET_NULL)
    category = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    is_broken = models.BooleanField(default=False, db_index=True)
    out_of_company = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return self.sn
    
    class Meta:
        ordering = ['-id']
    

def upload_to_uuid(instance, filename):
    ext = filename.split('.')[-1]
    return os.path.join('diagnosis_files/', f'{uuid.uuid4()}.{ext}')

def validate_is_pure_text(file):
    initial_pos = file.tell()
    file.seek(0)
    
    try:
        for chunk in file.chunks():
            if b'\0' in chunk:
                raise ValidationError('Plik zawiera dane binarne (null bytes). To nie jest czysty tekst.')
            try:
                chunk.decode('utf-8')
            except UnicodeDecodeError:
                raise ValidationError('Plik nie jest poprawnie zakodowanym tekstem UTF-8.')
                
    except ValidationError as e:
        raise e
    except Exception as e:
        raise ValidationError(f"Błąd analizy pliku: {e}")
    finally:
        file.seek(initial_pos)


class DiagnosisFile(models.Model):
    spea_card = models.ForeignKey(SpeaCard, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to=upload_to_uuid, validators=[
        FileExtensionValidator(allowed_extensions=['txt']),
        validate_is_pure_text
    ])
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['spea_card', '-created_at']),
        ]


class MoveLogSpea(models.Model):
    card = models.ForeignKey(SpeaCard, on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=255, db_index=True)
    date_time = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.card.sn} -- {self.movement_type}"