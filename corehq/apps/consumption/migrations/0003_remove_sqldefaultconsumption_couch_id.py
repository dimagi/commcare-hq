# -*- coding: utf-8 -*-
# Generated by Django 1.11.27 on 2020-02-07 20:16
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('consumption', '0002_populate_sqldefaultconsumption'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sqldefaultconsumption',
            name='couch_id',
        ),
    ]
