# Generated by Django 5.1.3 on 2025-03-05 08:25

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0005_remove_counterfromlastbackup_time_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='counterfromlastbackup',
            name='date',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
