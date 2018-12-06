# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-10-26 19:14
from __future__ import unicode_literals, absolute_import

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration


class Migration(migrations.Migration):

    # this migration requires those views to be generated
    # yet it shouldn't include more to allow adding columns to other views
    dependencies = [
        ('icds_reports', '0070_aww_name_in_agg_ccs_view'),
    ]
    sql_views = [
        'awc_location_months.sql',
        'agg_awc_monthly.sql',
        'agg_ccs_record_monthly.sql',
        'agg_child_health_monthly.sql',
    ]
    migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates', 'database_views'))
    operations = []
    for view in sql_views:
        operations.append(migrator.get_migration(view))
