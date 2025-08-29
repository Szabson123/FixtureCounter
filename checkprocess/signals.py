from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ProductProcess, NODE_TYPE_MAP

@receiver(post_save, sender=ProductProcess)
def create_related_model(sender, instance, created, **kwargs):
    if created and instance.type in NODE_TYPE_MAP:
        related_model = NODE_TYPE_MAP[instance.type]
        if not related_model.objects.filter(product_process=instance).exists():
            related_model.objects.create(product_process=instance)
