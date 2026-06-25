from django.db import models


class BaseSettings(models.Model):
    time_zone = models.CharField(max_length=255)
    manufacturer = models.CharField(max_length=255)
    plant = models.CharField(max_length=255)
    version = models.JSONField()


class Product(models.Model):
    base_settings = models.ForeignKey(BaseSettings, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)


class Station(models.Model):
    class StationType(models.TextChoices):
        'ICT' = 'ICT', 'ict'
        'FVT' = 'FVT', 'fvt'

    path = models.CharField(max_length=255)
    name = models.CharField(max_length=255)


