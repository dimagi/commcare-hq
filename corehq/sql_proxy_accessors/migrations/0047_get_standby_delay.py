from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_STANDBY_CLUSTER_NAME': settings.PL_PROXY_STANDBY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0046_get_ledger_values_for_cases_2'),
    ]

    operations = [
        migrator.get_migration('get_replication_delay.sql'),
    ]
