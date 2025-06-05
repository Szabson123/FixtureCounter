from django.db import models


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