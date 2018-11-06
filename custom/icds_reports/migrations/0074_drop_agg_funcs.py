# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0073_ccsrecordmonthly_closed'),
    ]

    operations = [
        migrations.RunSQL("DROP FUNCTION IF EXISTS aggregate_awc_daily(date)", "SELECT 1"),
        migrations.RunSQL("DROP FUNCTION IF EXISTS aggregate_awc_data(date)", "SELECT 1")
    ]
