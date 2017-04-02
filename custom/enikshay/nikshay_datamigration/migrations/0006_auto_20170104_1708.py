# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nikshay_datamigration', '0005_page_integer'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='followup',
            name='PatientID',
        ),
        migrations.DeleteModel(
            name='Followup',
        ),
    ]
