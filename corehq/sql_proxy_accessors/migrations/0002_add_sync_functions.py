# -*- coding: utf-8 -*-

from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0001_initial'),
    ]

    operations = [
        migrator.get_migration('get_case_last_modified_dates.sql'),
        migrator.get_migration('case_has_transactions_since_sync.sql'),
        migrator.get_migration('get_all_reverse_indices.sql'),
        migrator.get_migration('get_case_ids_modified_with_owner_since.sql'),
    ]
