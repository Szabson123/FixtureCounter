from django.db import models


class CollectorProduct(models.Model):
    name = models.CharField(max_length=255)


class DataBaseSettings(models.Model):
    ip = models.CharField(max_length=255)
    user = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    db_name = models.CharField(max_length=255)


class ProductStep(models.Model):
    c_product = models.ForeignKey(CollectorProduct, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=255, null=True, blank=True)
    data_base = models.ForeignKey(DataBaseSettings, on_delete=models.CASCADE)


class SettingsToProductProcess(models.Model):
    p_step = models.ForeignKey(ProductStep, on_delete=models.CASCADE)
    define_rule = models.CharField(max_length=255) # We will see for now placeholder