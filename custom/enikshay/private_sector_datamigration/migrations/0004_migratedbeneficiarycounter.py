# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-05-15 21:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('private_sector_datamigration', '0003_auto_20170513_1805'),
    ]

    operations = [
        migrations.CreateModel(
            name='MigratedBeneficiaryCounter',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
            ],
        ),
    ]
