from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0065_get_ledger_values_for_cases_3'),
    ]

    operations = [
        migrator.get_migration(
            'drop_get_case_ids_modified_with_owner_since.sql',
            'get_case_ids_modified_with_owner_since_1.sql',
        ),
    ]
