from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0048_get_ledger_values_for_cases_3'),
    ]

    operations = [
        migrator.get_migration(
            'drop_get_case_ids_modified_with_owner_since.sql',
            'get_case_ids_modified_with_owner_since.sql',
        ),
    ]
