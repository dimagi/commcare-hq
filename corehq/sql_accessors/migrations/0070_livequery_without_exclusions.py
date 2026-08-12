from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0069_drop_DELETED_references_fn'),
    ]

    operations = [
        migrator.get_migration('get_related_indices_without_exclusions.sql'),
    ]
