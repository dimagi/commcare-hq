# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nikshay_datamigration', '0003_add_outcome_again'),
    ]

    operations = [
        migrations.AlterField(
            model_name='outcome',
            name='PatientId',
            field=models.OneToOneField(related_name='outcome', primary_key=True, serialize=False, to='nikshay_datamigration.PatientDetail'),
        ),
    ]
