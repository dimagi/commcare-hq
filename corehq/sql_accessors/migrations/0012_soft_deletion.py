from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0011_get_case_types_for_domain'),
    ]

    operations = [
        migrator.get_migration('soft_delete_cases.sql'),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS update_form_state(TEXT, INTEGER)",
            "SELECT 1"
        ),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_forms_by_user_id(TEXT, TEXT, INTEGER);",
            "SELECT 1"
        )
    ]
