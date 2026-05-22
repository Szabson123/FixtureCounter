from django.db import models
import uuid

class Machine(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class FullValidationMachineModel(models.Model):
    unique_id = models.UUIDField(default=uuid.uuid4)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    is_valid = models.BooleanField(default=False)
    time_date = models.DateTimeField(null=True, blank=True)
    ended = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.machine.name} - {self.time_date} - {self.is_valid}"
    
    class Meta:
        ordering = ['-time_date']


class GoldenTypeValidate(models.Model):
    validation_model = models.ForeignKey(FullValidationMachineModel, on_delete=models.CASCADE, related_name='typesvalidate')
    side = models.IntegerField()
    good_golden = models.BooleanField(default=False)
    bad_golden = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.validation_model.machine.name} - {self.side} - Good Golden-{self.good_golden}, Bad Golden-{self.bad_golden}"


class EndedCodesWithQueue(models.Model):
    full_validation = models.ForeignKey(FullValidationMachineModel, on_delete=models.CASCADE, related_name='queues')
    code = models.CharField(max_length=255)
    queue = models.IntegerField()

    def __str__(self):
        return f"{self.full_validation.machine.name} - {self.code} - {self.queue}"


class TestedSn(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    sn = models.CharField(max_length=255)
    bin = models.JSONField()
    prev_phase = models.BooleanField()
    date_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_time']
        indexes = [
            models.Index(fields=['machine', 'sn', '-date_time'])
        ]
    
    def __str__(self):
        return f"{self.machine.name} - {self.sn}"