from django.db import models


class TestedParrotSn(models.Model):
    sn = models.CharField(max_length=255, db_index=True, unique=True)
    date = models.DateTimeField()
    done = models.BooleanField()
    error = models.TextField(null=True, blank=True)
    internal_code = models.CharField(max_length=255, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['date', 'id', 'sn'], name='parrot_date_id_sn_idx'),
            models.Index(fields=['date', 'done', 'internal_code'], name='parrot_date_done_ic_idx'),
        ]