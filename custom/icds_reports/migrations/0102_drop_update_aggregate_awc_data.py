# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0101_add_supervisor_id'),
    ]

    operations = [
        migrations.RunSQL('DROP FUNCTION IF EXISTS update_aggregate_awc_data(date)')
    ]
