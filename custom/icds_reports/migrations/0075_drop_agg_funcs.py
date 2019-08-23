# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0074_expected_decimal'),
    ]

    operations = [
        migrations.RunSQL("DROP FUNCTION IF EXISTS aggregate_awc_daily(date)", "SELECT 1"),
        migrations.RunSQL("DROP FUNCTION IF EXISTS aggregate_awc_data(date)", "SELECT 1")
    ]
