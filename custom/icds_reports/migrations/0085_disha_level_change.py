# -*- coding: utf-8 -*-
# Generated by Django 1.11.14 on 2018-08-20 09:20
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration


def get_all_disha_migrations():
    sql_views = [
        'agg_awc_monthly.sql',
        'agg_ccs_record_monthly.sql',
        'agg_child_health_monthly.sql',
        'disha_indicators.sql',
    ]
    migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates', 'database_views'))
    operations = []
    for view in sql_views:
        operations.append(migrator.get_migration(view))
    return operations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0084_anc_abnormalities'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dishaindicatorview',
            name='awc_id',
        ),
        migrations.RemoveField(
            model_name='dishaindicatorview',
            name='awc_name',
        ),
        migrations.RemoveField(
            model_name='dishaindicatorview',
            name='supervisor_id',
        ),
        migrations.RemoveField(
            model_name='dishaindicatorview',
            name='supervisor_name',
        )
    ]
