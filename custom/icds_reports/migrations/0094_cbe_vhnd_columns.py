# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0093_pse_days_21'),
    ]

    operations = [
        migrator.get_migration('update_tables40.sql')
    ]
