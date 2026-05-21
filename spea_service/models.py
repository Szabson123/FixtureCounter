from django.db import models
import uuid

class Machine(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class FullValidationMachineModel(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    is_valid = models.BooleanField(default=False)
    date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.machine.name} - {self.date} - {self.is_valid}"


class EndedCodesWithQueue(models.Model):
    full_validation = models.ForeignKey(FullValidationMachineModel, on_delete=models.CASCADE, related_name='queues')
    code = models.CharField(max_length=255)
    queue = models.IntegerField()

    def __str__(self):
        return f"{self.full_validation.machine.name} - {self.code} - {self.queue}"


class UniqueTestValue(models.Model):
    unique_batch_id = models.UUIDField(default=uuid.uuid4)
    date = models.DateTimeField(auto_now_add=True)


class TestedSn(models.Model):
    test_num = models.ForeignKey(UniqueTestValue, on_delete=models.CASCADE)
    sn = models.CharField(max_length=255)
    bin = models.JSONField()
    prev_phase = models.BooleanField()