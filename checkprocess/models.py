from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class ProductProcess(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='processes')
    name = models.CharField(max_length=255)
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} → {self.name} (order: {self.order})"


class ProductObject(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_objects')
    serial_number = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expire_date = models.DateField(null=True, blank=True, default=None)

    def __str__(self):
        return f"{self.serial_number} ({self.product.name})"


class ProductObjectProcess(models.Model):
    product_object = models.ForeignKey(ProductObject, on_delete=models.CASCADE, related_name='assigned_processes')
    process = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, related_name='assigned_processes')
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('product_object', 'process')

    def __str__(self):
        status = "✓" if self.is_completed else "✗"
        return f"{self.product_object.serial_number} - {self.process.name} [{status}]"


class ProductObjectProcessLog(models.Model):
    product_object_process = models.ForeignKey(ProductObjectProcess, on_delete=models.CASCADE, related_name='logs')
    entry_time = models.DateTimeField(auto_now_add=True)
    who_entry = models.CharField(max_length=255, null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    who_exit = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Log for {self.product_object_process} @ {self.entry_time:%Y-%m-%d %H:%M}"
