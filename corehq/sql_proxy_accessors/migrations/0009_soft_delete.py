from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0008_get_case_types_for_domain'),
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
