# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-05-18 22:37
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('case_search', '0005_migrate_json_config'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='casesearchconfig',
            name='_config',
        ),
    ]
