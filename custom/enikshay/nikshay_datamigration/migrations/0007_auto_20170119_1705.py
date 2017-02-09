# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nikshay_datamigration', '0006_auto_20170104_1708'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patientdetail',
            name='dotmosdone',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='patientdetail',
            name='paddress',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
