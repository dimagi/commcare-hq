# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-02-21 09:32
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0099_service_delivery_report'),
    ]

    operations = [
        migrations.AddField(
            model_name='aggregatebirthpreparednesforms',
            name='supervisor_id',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='aggregateccsrecorddeliveryforms',
            name='supervisor_id',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='aggregateccsrecordpostnatalcareforms',
            name='supervisor_id',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='aggregateccsrecordthrforms',
            name='supervisor_id',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='aggregatecomplementaryfeedingforms',
            name='supervisor_id',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='awwincentivereport',
            name='supervisor_id',
            field=models.TextField(null=True),
        ),
    ]
