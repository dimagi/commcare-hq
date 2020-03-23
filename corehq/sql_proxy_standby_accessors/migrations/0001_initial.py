from django.conf import settings
from django.db import migrations

from corehq.sql_db.config import plproxy_standby_config
from corehq.sql_db.management.commands.configure_pl_proxy_cluster import (
    get_drop_server_sql,
    get_sql_to_create_pl_proxy_cluster,
)
from corehq.sql_db.operations import RawSQLMigration
from corehq.util.django_migrations import noop_migration

migrator = RawSQLMigration(('corehq', 'sql_proxy_standby_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


def create_update_pl_proxy_config():
    if not plproxy_standby_config or not (settings.UNIT_TESTING and settings.USE_PARTITIONED_DATABASE):
        return noop_migration()

    sql_statements = get_sql_to_create_pl_proxy_cluster(plproxy_standby_config)
    drop_server_sql = get_drop_server_sql(plproxy_standby_config.cluster_name)
    return migrations.RunSQL('\n'.join(sql_statements), drop_server_sql)


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunSQL(
            'CREATE EXTENSION IF NOT EXISTS plproxy',
            'DROP EXTENSION plproxy'
        ),
        migrations.RunSQL(
            'CREATE EXTENSION IF NOT EXISTS hashli',
            'DROP EXTENSION hashli'
        ),
        create_update_pl_proxy_config(),
        migrator.get_migration('get_replication_delay.sql'),
    ]
