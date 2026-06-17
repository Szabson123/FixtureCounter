from django.db import models
from django.core.validators import MaxValueValidator


class PasswordToUnlock(models.Model):
    passw = models.CharField(max_length=255)
    who = models.CharField(max_length=255)


class CheckMachine(models.Model):
    phase_id = models.IntegerField(unique=True)
    counter = models.IntegerField(
        verbose_name="Counter",
        validators=[MaxValueValidator(200)], 
        default=1
    )

    def __str__(self):
        return f"{self.phase_id}"
    

class UnlockHistory(models.Model):
    phase_id = models.IntegerField()
    internal_code = models.IntegerField()
    who = models.CharField(max_length=255)

    date_time = models.DateTimeField(auto_now_add=True)