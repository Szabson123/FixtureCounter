# Generated by Django 5.1.3 on 2025-07-03 10:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('checkprocess', '0023_backmapprocess'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='productobject',
            name='re_use',
        ),
        migrations.RemoveField(
            model_name='productobjectprocess',
            name='completed_at',
        ),
        migrations.RemoveField(
            model_name='productobjectprocess',
            name='is_completed',
        ),
        migrations.RemoveField(
            model_name='productprocess',
            name='can_multi',
        ),
    ]
