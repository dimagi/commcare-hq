# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0024_rename_case_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseforms',
            name='server_date',
            field=models.DateTimeField(default=datetime.datetime(2015, 11, 13, 9, 21, 40, 422766)),
            preserve_default=False,
        ),
    ]
