# Generated by Django 1.11.12 on 2018-04-26 18:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0016_location_type_filter'),
    ]

    operations = [
        migrations.AlterField(
            model_name='alertschedule',
            name='ui_type',
            field=models.CharField(default='X', max_length=2),
        ),
        migrations.AlterField(
            model_name='timedschedule',
            name='ui_type',
            field=models.CharField(default='X', max_length=2),
        ),
    ]
