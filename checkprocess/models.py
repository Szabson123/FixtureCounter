from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=255)
    child_limit = models.IntegerField(null=True, blank=True, default=20)

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
    
    respect_quranteen_time = models.BooleanField(default=False)
    expecting_child = models.BooleanField(default=False)
    killing_app = models.BooleanField(default=False)
    ending_process = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} → {self.name} (order: {self.order})"
    

class Place(models.Model):
    name = models.CharField(max_length=255)
    process = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, related_name='assigned_place', null=True, blank=True, default=None)
    only_one_product_object = models.BooleanField(default=False)
    
    def __str__(self) -> str:
        return self.name


class ProductObject(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_objects')
    mother_object = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_object')
    is_mother = models.BooleanField(default=False)
    
    current_process = models.ForeignKey(ProductProcess, on_delete=models.SET_NULL, null=True, blank=True)
    current_place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True)
    
    serial_number = models.CharField(max_length=255, unique=True, db_index=True)
    full_sn = models.CharField(max_length=255, unique=True, db_index=True, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expire_date = models.DateField(null=True, blank=True, default=None)
    production_date = models.DateField(null=True, blank=True, default=None)
    exp_date_in_process = models.DateField(null=True, blank=True, default=None)
    quranteen_time = models.DateTimeField(null=True, blank=True, default=None)
    
    ex_mother = models.CharField(max_length=255, null=True, blank=True)
    
    re_use = models.BooleanField(default=False)
    end = models.BooleanField(default=False)

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
    place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True, related_name="process_logs")

    def __str__(self):
        return f"Log for {self.product_object_process} @ {self.entry_time:%Y-%m-%d %H:%M}"


class AppToKill(models.Model):
    line_name = models.ForeignKey(Place, models.CASCADE)
    killing_flag = models.BooleanField(default=False)
    