# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-10-16 21:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0013_subscription_dates_check'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentmethod',
            name='web_user',
            field=models.CharField(db_index=True, max_length=80),
        ),
    ]
