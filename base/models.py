from django.db import models


class CounterSumFromLastMaint(models.Model):
    counter = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.counter}"
    

class FullCounter(models.Model):
    counter = models.IntegerField(default=1)
    

class Fixture(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_date = models.DateTimeField(auto_now_add=True)
    counter_all= models.ForeignKey(FullCounter, on_delete=models.CASCADE, null=True, blank=True)
    counter_last_maint = models.ForeignKey(CounterSumFromLastMaint, on_delete=models.CASCADE, null=True, blank=True)
    cycles_limit = models.IntegerField(default=50_000)
    
    def __str__(self) -> str:
        return f'{self.name}'
    

class Counter(models.Model):
    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name='counter', null=True, blank=True)
    time_date = models.DateTimeField(auto_now_add=True)
    

class CounterHistory(models.Model):
    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, null=True, blank=True, related_name='backup')
    date = models.DateTimeField(auto_now_add=True)
    counter = models.IntegerField()

    def __str__(self):
        return f'{self.fixture.name}' if self.fixture else 'No Fixture'
    

class Machine(models.Model):
    machine_id = models.CharField(max_length=255, null=True, blank=True)
    machine_name = models.CharField(max_length=255)


class MachineCondition(models.Model):
    machine = models.OneToOneField(Machine, on_delete=models.CASCADE)
    last_variant = models.CharField(max_length=255, null=True, blank=True)