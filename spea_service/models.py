from django.db import models


class Machine(models.Model):
    name = models.CharField(max_length=255)


class FullValidationMachineModel(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    is_valid = models.BooleanField(default=False)
    date = models.DateTimeField(null=True, blank=True)


class EndedCodesWithQueue(models.Model):
    full_validation = models.ForeignKey(FullValidationMachineModel, on_delete=models.CASCADE, related_name='queues')
    code = models.CharField(max_length=255)
    queue = models.IntegerField()


