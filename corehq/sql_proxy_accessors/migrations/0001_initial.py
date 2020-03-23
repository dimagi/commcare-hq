from django.conf import settings
from django.db import migrations

from corehq.sql_db.config import plproxy_config
from corehq.sql_db.management.commands.configure_pl_proxy_cluster import (
    get_drop_server_sql,
    get_sql_to_create_pl_proxy_cluster,
)
from corehq.sql_db.operations import RawSQLMigration
from corehq.util.django_migrations import noop_migration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


def create_update_pl_proxy_config():
    if not (settings.UNIT_TESTING and settings.USE_PARTITIONED_DATABASE):
        return noop_migration()

    sql_statements = get_sql_to_create_pl_proxy_cluster(plproxy_config)
    drop_server_sql = get_drop_server_sql(plproxy_config.cluster_name)
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
        migrator.get_migration('archive_unarchive_form.sql'),
        migrator.get_migration('get_case_by_location_id.sql'),
        migrator.get_migration('get_cases_by_id.sql'),
        migrator.get_migration('get_form_attachment_by_name.sql'),
        migrator.get_migration('get_forms_by_id.sql'),
        migrator.get_migration('get_forms_by_state.sql'),
        migrator.get_migration('get_multiple_cases_indices.sql'),
        migrator.get_migration('get_multiple_forms_attachments.sql'),
        migrator.get_migration('hard_delete_cases.sql'),
        migrator.get_migration('revoke_restore_case_transactions_for_form.sql'),
        migrator.get_migration('update_form_problem_and_state.sql'),
    ]
