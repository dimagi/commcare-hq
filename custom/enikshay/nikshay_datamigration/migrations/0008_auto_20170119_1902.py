# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nikshay_datamigration', '0007_auto_20170119_1705'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='outcome',
            name='OutcomeDate1',
        ),
        migrations.RemoveField(
            model_name='outcome',
            name='loginDate',
        ),
    ]
