# Generated by Django 3.2.23 on 2023-11-20 06:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0021_datasourcechangesubscriber_datasourcerowtransactionlog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datasourcerowtransactionlog',
            name='action',
            field=models.CharField(choices=[('upsert', 'upsert'), ('delete', 'delete')], max_length=32),
        ),
    ]
