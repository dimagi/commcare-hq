# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-03-20 16:30
from __future__ import absolute_import
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0016_createscheduleinstanceactiondefinition_specific_start_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='domaincaserulerun',
            name='dbs_completed',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=list),
        ),
        migrations.AlterField(
            model_name='domaincaserulerun',
            name='cases_checked',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='domaincaserulerun',
            name='num_closes',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='domaincaserulerun',
            name='num_creates',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='domaincaserulerun',
            name='num_related_closes',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='domaincaserulerun',
            name='num_related_updates',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='domaincaserulerun',
            name='num_updates',
            field=models.IntegerField(default=0),
        ),
    ]
