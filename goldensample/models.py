from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

GoldenTypes = [
    ('good', 'Good'),
    ('bad', 'Bad'),
    ('calib', 'Calib')
]


class GroupVariantCode(models.Model):
    name = models.CharField(max_length=255)
    last_time_tested = models.DateTimeField(blank=True, null=True, default=None)

    def __str__(self):
        return self.name


class VariantCode(models.Model):
    code = models.CharField(max_length=255)
    group = models.ForeignKey(GroupVariantCode, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.code
    
    @property
    def counter(self):
        return sum(
            g.counterongolden.counter
            for g in self.goldensample_set.all()
            if hasattr(g, 'counterongolden')
        )


class GoldenSample(models.Model):
    variant = models.ForeignKey(VariantCode, on_delete=models.CASCADE)
    golden_code = models.CharField(max_length=255)
    expire_date = models.DateField()
    type_golden = models.CharField(choices=GoldenTypes, max_length=255)

    def __str__(self):
        return f"{self.golden_code} ({self.type_golden})"
    

class CounterOnGolden(models.Model):
    golden_sample = models.OneToOneField(GoldenSample, on_delete=models.CASCADE)
    counter = models.IntegerField(default=0)
    

class MapSample(models.Model):
    i_input = models.CharField(max_length=255)
    i_output = models.CharField(max_length=255)
    
    def __str__(self) -> str:
        return f"{self.i_input} to {self.i_output}"


class PcbEvent(models.Model):
    group = models.ForeignKey(GroupVariantCode, null=True, blank=True, on_delete=models.SET_NULL, related_name="pcb_events")
    sn = models.CharField(max_length=255)
    result = models.BooleanField(null=True, blank=True)
    time_date_tested = models.DateTimeField(auto_now_add=True)
    shared_plate = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["sn", "time_date_tested"]),
            models.Index(fields=["shared_plate", "result"]),
        ]
        ordering = ["-time_date_tested"]

    def __str__(self):
        return f"{self.sn} -- {self.result}"
    

class TimerGroup(models.Model):
    time_date = models.DateTimeField()


class CodeSmd(models.Model):
    timer_group = models.ForeignKey(TimerGroup, on_delete=models.CASCADE, null=True, blank=True)
    code = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.code


class ClientName(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class ProcessName(models.Model):
    name = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name

class TypeName(models.Model):
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.name

class Department(models.Model):
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.name

class EndCode(models.Model):
    code = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.code
    
    
class MasterSample(models.Model):
    code_smd = models.ManyToManyField(CodeSmd, blank=True)
    endcodes = models.ManyToManyField(EndCode, blank=True) 
    client = models.ForeignKey(ClientName, on_delete=models.SET_NULL, null=True, blank=True)
    process_name = models.ForeignKey(ProcessName, on_delete=models.CASCADE)
    master_type = models.ForeignKey(TypeName, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    departament = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True)

    details = models.TextField(null=True, blank=True)
    comennt = models.TextField(null=True, blank=True)

    # endcodes -> multi
    project_name = models.CharField(max_length=255)
    sn = models.CharField(max_length=255)
    date_created = models.DateField(auto_now_add=True)
    expire_date = models.DateField()
    pcb_rev_code = models.CharField(max_length=255)
    counter = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.sn
   

class MachineGoldensTime(models.Model):
    machine_name = models.CharField(max_length=255, unique=True)
    date_time = models.DateTimeField()