# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ilsgateway', '0005_add_pending_reporting_data_recalculation'),
    ]

    operations = [
        migrations.DeleteModel(
            name='SupplyPointWarehouseRecord',
        )
    ]
