# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-05-05 16:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0004_auto_20170330_2049'),
    ]

    operations = [
        migrations.AddField(
            model_name='asyncindicator',
            name='unsuccessful_attempts',
            field=models.IntegerField(default=0),
        ),
    ]
