# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logistics', '0002_auto_20151204_2142'),
    ]

    operations = [
        migrations.DeleteModel(
            name='MigrationCheckpoint',
        ),
        migrations.RemoveField(
            model_name='stockdatacheckpoint',
            name='location',
        ),
        migrations.DeleteModel(
            name='StockDataCheckpoint',
        ),
    ]
