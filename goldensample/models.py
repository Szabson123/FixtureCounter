from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

    
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
    compute_name = models.CharField(max_length=255, null=True, blank=True)
    
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
    sn = models.CharField(max_length=255, unique=True)
    date_created = models.DateField(auto_now_add=True)
    expire_date = models.DateField()
    pcb_rev_code = models.CharField(max_length=255)
    counter = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.sn
   

class MachineGoldensTime(models.Model):
    machine_name = models.CharField(max_length=255, unique=True)
    date_time = models.DateTimeField()

    def __str__(self):
        return self.machine_name


class EndCodeTimeFWK(models.Model):
    machine_id = models.CharField(max_length=255)
    site = models.PositiveIntegerField(null=True, blank=True)
    last_good_tested = models.DateTimeField(null=True, blank=True)
    endcode = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.machine_id} - {self.site} - {self.endcode}, date: {self.last_good_tested}"


class LastResultFWK(models.Model): #remember its not sn to its result 
    sn = models.CharField(max_length=255)
    result = models.CharField(max_length=255, null=True, blank=True)
    date_time_tested = models.DateTimeField(auto_now_add=True)
    machine_id = models.CharField(max_length=255)
    site = models.PositiveIntegerField()

    def __str__(self):
        return f'{self.machine_id} site {self.site}'


class TempCheckMasterFWK(models.Model):
    machine_id = models.CharField(max_length=255)
    site = models.PositiveIntegerField()
    pass_res = models.BooleanField(null=True)
    fail_res = models.BooleanField(null=True)

    def __str__(self):
        return f'{self.machine_id} site {self.site}'


class TempMasterShow(models.Model):
    machine_id = models.CharField(max_length=255)
    site = models.PositiveIntegerField()
    if_set = models.BooleanField(default=False)
    sn = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.machine_id} site {self.site}'