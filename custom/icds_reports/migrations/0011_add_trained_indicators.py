# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0010_change_active_definition'),
    ]

    operations = [
        migrator.get_migration('update_tables6.sql'),
    ]
