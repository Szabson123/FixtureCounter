# Generated by Django 5.1.3 on 2024-12-05 08:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0002_alter_fixture_counter_summ'),
    ]

    operations = [
        migrations.CreateModel(
            name='CounterFromLastBackup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('summ', models.IntegerField()),
                ('fixture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='backup', to='base.fixture')),
            ],
        ),
    ]
