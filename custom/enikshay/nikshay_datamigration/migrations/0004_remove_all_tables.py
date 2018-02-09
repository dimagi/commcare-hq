# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nikshay_datamigration', '0003_add_outcome_again'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='followup',
            name='PatientID',
        ),
        migrations.RemoveField(
            model_name='outcome',
            name='PatientId',
        ),
        migrations.DeleteModel(
            name='Followup',
        ),
        migrations.DeleteModel(
            name='Outcome',
        ),
        migrations.DeleteModel(
            name='PatientDetail',
        ),
    ]
