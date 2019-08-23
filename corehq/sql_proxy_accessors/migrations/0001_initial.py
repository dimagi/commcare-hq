# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.conf import settings
from django.db import migrations

from corehq.sql_db.config import partition_config
from corehq.sql_db.management.commands.configure_pl_proxy_cluster import get_drop_server_sql, \
    get_pl_proxy_server_config_sql, get_user_mapping_sql
from corehq.sql_db.operations import RawSQLMigration
from corehq.util.django_migrations import noop_migration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


def create_update_pl_proxy_config():
    if not (settings.UNIT_TESTING and settings.USE_PARTITIONED_DATABASE):
        return noop_migration()

    drop_server_sql = get_drop_server_sql()
    sql_statements = [
        get_pl_proxy_server_config_sql(partition_config.get_shards()),
        get_user_mapping_sql()
    ]

    return migrations.RunSQL(
        '\n'.join(sql_statements),
        drop_server_sql
    )


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunSQL(
            'CREATE EXTENSION IF NOT EXISTS plproxy',
            'DROP EXTENSION plproxy'
        ),
        migrations.RunSQL(
            'CREATE EXTENSION IF NOT EXISTS hashlib',
            'DROP EXTENSION hashlib'
        ),
        create_update_pl_proxy_config(),
        migrator.get_migration('archive_unarchive_form.sql'),
        migrator.get_migration('check_form_exists.sql'),
        migrator.get_migration('get_case_attachments.sql'),
        migrator.get_migration('get_case_by_id.sql'),
        migrator.get_migration('get_case_by_location_id.sql'),
        migrator.get_migration('get_case_transactions.sql'),
        migrator.get_migration('get_cases_by_id.sql'),
        migrator.get_migration('get_form_attachment_by_name.sql'),
        migrator.get_migration('get_form_attachments.sql'),
        migrator.get_migration('get_form_operations.sql'),
        migrator.get_migration('get_forms_by_id.sql'),
        migrator.get_migration('get_forms_by_state.sql'),
        migrator.get_migration('get_multiple_cases_indices.sql'),
        migrator.get_migration('get_multiple_forms_attachments.sql'),
        migrator.get_migration('hard_delete_cases.sql'),
        migrator.get_migration('revoke_restore_case_transactions_for_form.sql'),
        migrator.get_migration('update_form_problem_and_state.sql'),
    ]
