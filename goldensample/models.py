from django.db import models


GoldenTypes = [
    ('good', 'Good'),
    ('bad', 'Bad'),
    ('calib', 'Calib')
]


class GroupVariantCode(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class VariantCode(models.Model):
    code = models.CharField(max_length=255)
    group = models.ForeignKey(GroupVariantCode, on_delete=models.CASCADE)

    def __str__(self):
        return self.code


class GoldenSample(models.Model):
    variant = models.ForeignKey(VariantCode, on_delete=models.CASCADE)
    golden_code = models.CharField(max_length=255)
    expire_date = models.DateField()
    type_golden = models.CharField(choices=GoldenTypes, max_length=255)

    def __str__(self):
        return f"{self.golden_code} ({self.type_golden})"