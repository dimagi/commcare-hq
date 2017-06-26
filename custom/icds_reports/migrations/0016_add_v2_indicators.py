# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0015_add_aggregation_level'),
    ]

    operations = [
        migrator.get_migration('update_tables9.sql'),
        migrator.get_migration('setup_agg_awc_daily.sql'),
        migrator.get_migration('create_datasource_views.sql'),
    ]
