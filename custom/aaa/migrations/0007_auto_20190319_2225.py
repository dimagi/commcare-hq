# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-03-19 22:25
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aaa', '0006_auto_20190225_1900'),
    ]

    operations = [
        migrations.AddField(
            model_name='ccsrecord',
            name='num_anc_checkups',
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='ccsrecord',
            name='pnc1_date',
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name='ccsrecord',
            name='pnc2_date',
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name='ccsrecord',
            name='pnc3_date',
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name='ccsrecord',
            name='pnc4_date',
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='last_immunization_date',
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='last_immunization_type',
            field=models.TextField(null=True),
        ),
    ]
