# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-12-13 09:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('phonelog', '0014_auto_20170718_2039'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devicereportentry',
            name='id',
            field=models.BigAutoField(primary_key=True, serialize=False)
        )
    ]
