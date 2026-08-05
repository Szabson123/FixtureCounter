from django.db import models
import uuid

def get_uuid():
    return uuid.uuid4

class TestedParrotSn(models.Model):
    sn = models.CharField(max_length=255, db_index=True, unique=True)
    date = models.DateTimeField()
    done = models.BooleanField()
    error = models.TextField(null=True, blank=True)
    internal_code = models.CharField(max_length=255, db_index=True)
    certyficate = models.CharField(max_length=255, unique=True, db_index=True, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['date', 'id', 'sn'], name='parrot_date_id_sn_idx'),
            models.Index(fields=['date', 'done', 'internal_code'], name='parrot_date_done_ic_idx'),
            models.Index(fields=['certyficate', 'done'], name='parrot_cert_done_idx'),
        ]