
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports',
         '0025_add_fully_immunized_to_view'),
    ]

    operations = [
        migrator.get_migration('update_tables11.sql'),
    ]
