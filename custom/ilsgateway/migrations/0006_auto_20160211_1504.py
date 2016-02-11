# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('ilsgateway', '0005_add_pending_reporting_data_recalculation'),
    ]

    operations = [
        migrations.AddField(
            model_name='reportrun',
            name='updating_historical_data',
            field=models.BooleanField(default=False),
            preserve_default=True,
        )
    ]
