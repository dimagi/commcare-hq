from __future__ import absolute_import, unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0083_ccs_record_monthly_pregnant_all'),
    ]

    operations = [
        migrator.get_migration('update_tables35.sql')
    ]
