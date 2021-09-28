from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0064_remove_get_case_models_functions'),
    ]

    operations = [
        migrator.get_migration('get_ledger_values_for_cases_3.sql'),
    ]
