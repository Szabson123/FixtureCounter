from django.db import models


class BaseSettings(models.Model):
    time_zone = models.CharField(max_length=255)
    manufacturer = models.CharField(max_length=255)
    plant = models.CharField(max_length=255)
    version = models.JSONField()


class Product(models.Model):
    base_settings = models.ForeignKey(BaseSettings, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=False)


class Task(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    done = models.BooleanField(null=True, default=False)
    date = models.DateTimeField(auto_now_add=True)
    error_code = models.CharField(null=True, blank=True)


class Station(models.Model):
    class StationType(models.TextChoices):
        ICT = 'ICT', 'ict'
        FVT = 'FVT', 'fvt'

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    path = models.CharField(max_length=255)
    test_station_name = models.CharField(max_length=255)
    s_type = models.CharField(choices=StationType, max_length=255)
    line_splitter = models.CharField(max_length=1, default=';')
    queue = models.IntegerField(null=True)


class StationStage(models.Model):
    class TestType(models.TextChoices):
        GETE = 'GETE', 'gte'
        EQ = 'EQ', 'eq'
        GTLT = 'GTLT', 'gtlt'
        CMD = 'CMD', 'cmd'

    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    test_type = models.CharField(max_length=255)
    pattern_1 = models.CharField(max_length=255)
    pattern_2 = models.CharField(max_length=255, null=True, blank=True)
    pattern_3 = models.CharField(max_length=255, null=True, blank=True)


class HeaderDataStation(models.Model):
    station = models.OneToOneField(Station, on_delete=models.CASCADE)
    sn = models.CharField(max_length=255, db_index=True, unique=True, null=True, blank=True)
    partnumber = models.CharField(max_length=255, null=True, blank=True)
    decoded_serial = models.CharField(max_length=255, null=True, blank=True)
    devicetype = models.CharField(max_length=255, null=True, blank=True)
    hw_version = models.CharField(max_length=255, null=True, blank=True)
    bootloader_version = models.CharField(max_length=255, null=True, blank=True)
    mac = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.sn}'