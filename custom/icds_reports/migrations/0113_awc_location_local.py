# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration
from custom.icds_reports.utils.migrations import get_view_migrations

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates', 'database_views'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0112_daily_attendance_index'),
    ]

    operations = [
        migrations.RunSQL('CREATE TABLE IF NOT EXISTS "icds_months_local" (LIKE "icds_months" INCLUDING ALL)'),
        migrations.RunSQL('CREATE TABLE IF NOT EXISTS "awc_location_local" (LIKE "awc_location" INCLUDING ALL)')
    ]
    operations.extend(get_view_migrations())
    operations.append(migrator.get_migration('service_delivery_monthly.sql'),)
