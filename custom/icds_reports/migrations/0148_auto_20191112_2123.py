# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-11-12 21:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0147_mwcd_report_view'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aggregationrecord',
            name='run_date',
            field=models.DateField(),
        ),
    ]
