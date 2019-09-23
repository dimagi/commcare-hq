from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0036_exclude_deleted'),
    ]

    operations = [
        migrator.get_migration('hard_delete_cases_2.sql'),
    ]
