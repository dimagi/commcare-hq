# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-02 15:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rch', '0004_auto_20170219_1810'),
    ]

    operations = [
        migrations.AddField(
            model_name='rchchild',
            name='cas_case_id',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='cas_case_id',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
