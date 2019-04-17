# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

from custom.icds_reports.utils.migrations import get_view_migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0112_aww_incentive_report_monthly'),
    ]

    operations = [
        migrations.RunSQL('CREATE TABLE IF NOT EXISTS "icds_months_local" (LIKE "icds_months" INCLUDING ALL)'),
        migrations.RunSQL('CREATE TABLE IF NOT EXISTS "awc_location_local" (LIKE "awc_location" INCLUDING ALL)')
    ]
    operations.extend(get_view_migrations())
