# Generated by Django 5.1.3 on 2025-03-05 10:24

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0007_fullcounter_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CounterHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('counter', models.IntegerField()),
                ('fixture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='backup', to='base.fixture')),
            ],
        ),
        migrations.DeleteModel(
            name='CounterFromLastBackup',
        ),
    ]
