# Generated by Django 5.1.3 on 2025-06-23 07:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('checkprocess', '0013_productprocess_respect_quranteen_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='productobject',
            name='is_mother',
            field=models.BooleanField(default=False),
        ),
    ]
