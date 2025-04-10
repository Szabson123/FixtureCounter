from django.db import models


class Object(models.Model):
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=7)
    