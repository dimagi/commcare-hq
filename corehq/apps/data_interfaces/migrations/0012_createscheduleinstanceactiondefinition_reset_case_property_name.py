# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-21 15:36
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0011_domaincaserulerun_num_creates'),
    ]

    operations = [
        migrations.AddField(
            model_name='createscheduleinstanceactiondefinition',
            name='reset_case_property_name',
            field=models.CharField(max_length=126, null=True),
        ),
    ]
