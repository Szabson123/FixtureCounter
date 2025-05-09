from django.db import models


class ProductFamily(models.Model):
    name = models.CharField(max_length=255)
    

class VariantCode(models.Model):
    product_family = models.ForeignKey(ProductFamily, on_delete=models.CASCADE)
    code = models.CharField(max_length=255)
    

class GoldenSampleCode(models.Model):
    variant_code = models.ForeignKey(VariantCode, on_delete=models.CASCADE)
    sample_code = models.CharField(max_length=255)