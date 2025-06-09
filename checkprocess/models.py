from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=255)    


class ProductProcess(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='processes')
    name = models.CharField(max_length=255)
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order'] 
