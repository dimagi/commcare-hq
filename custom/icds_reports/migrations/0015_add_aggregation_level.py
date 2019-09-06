from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0014_add_datasource_views'),
    ]

    operations = [
        migrator.get_migration('update_tables8.sql')
    ]
