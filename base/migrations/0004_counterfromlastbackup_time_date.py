# Generated by Django 5.1.3 on 2024-12-05 08:56

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0003_counterfromlastbackup'),
    ]

    operations = [
        migrations.AddField(
            model_name='counterfromlastbackup',
            name='time_date',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
