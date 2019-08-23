# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0076_awc_locations_test_columns'),
    ]

    operations = [
        migrations.RunSQL("DROP FUNCTION IF EXISTS aggregate_location_table()", "SELECT 1"),
        migrations.RunSQL("DROP FUNCTION IF EXISTS update_location_table()", "SELECT 1"),
        migrations.RunSQL("DROP FUNCTION IF EXISTS insert_into_daily_attendance(date)", "SELECT 1")
    ]
