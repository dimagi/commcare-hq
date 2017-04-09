# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rch', '0002_rchmother_mdds_villageid'),
    ]

    operations = [
        migrations.RenameField(
            model_name='rchchild',
            old_name='VILLAGE_Name',
            new_name='Village_Name',
        ),
        migrations.RemoveField(
            model_name='rchmother',
            name='Village_ID',
        ),
    ]
