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
    
    # specyfic process types
    can_multi = models.BooleanField(default=False)
    changing_exp_date = models.BooleanField(default=False)
    how_much_days_exp_date = models.IntegerField(default=None, blank=True, null=True)
    quranteen_time = models.IntegerField(default=None, blank=True, null=True)
    

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} → {self.name} (order: {self.order})"
    

class Place(models.Model):
    name = models.CharField(max_length=255)
    process = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, related_name='assigned_place', null=True, blank=True, default=None)
    
    def __str__(self) -> str:
        return self.name


class ProductObject(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_objects')
    mother_object = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_object')
    
    current_process = models.ForeignKey(ProductProcess, on_delete=models.SET_NULL, null=True, blank=True)
    current_place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True)
    
    serial_number = models.CharField(max_length=255, unique=True, db_index=True)
    full_sn = models.CharField(max_length=255, unique=True, db_index=True, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expire_date = models.DateField(null=True, blank=True, default=None)
    production_date = models.DateField(null=True, blank=True, default=None)
    exp_date_in_process = models.DateField(null=True, blank=True, default=None)

    def __str__(self):
        return f"{self.serial_number} ({self.product.name})"


class ProductObjectProcess(models.Model):
    product_object = models.ForeignKey(ProductObject, on_delete=models.CASCADE, related_name='assigned_processes')
    process = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, related_name='assigned_processes')
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_end = models.BooleanField(default=False)

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
    place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True, related_name="process_logs")

    def __str__(self):
        return f"Log for {self.product_object_process} @ {self.entry_time:%Y-%m-%d %H:%M}"

