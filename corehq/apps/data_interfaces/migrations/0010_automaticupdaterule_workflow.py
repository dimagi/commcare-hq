# Generated by Django 1.10.7 on 2017-05-23 11:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0009_scheduling_integration'),
    ]

    operations = [
        migrations.AddField(
            model_name='automaticupdaterule',
            name='workflow',
            field=models.CharField(default='CASE_UPDATE', max_length=126),
            preserve_default=False,
        ),
    ]
