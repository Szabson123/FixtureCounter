from django.db import models


class ObjectProcess(models.Model):
    name = models.CharField(max_length=255)
    been = models.BooleanField(default=False)
    is_required = models.BooleanField(default=True)


class BigObject(models.Model):
    name = models.CharField(max_length=255)
    big_object = models.OneToOneField(ObjectProcess, on_delete=models.CASCADE, null=True, blank=True, default=None)
    

class SmallObject(models.Model):
    mother = models.ForeignKey(BigObject, on_delete=models.CASCADE, null=True, blank=True, related_name='small_object')
    name = models.CharField(max_length=255)
    process = models.OneToOneField(ObjectProcess, on_delete=models.CASCADE, null=True, blank=True, default=None)
    
    