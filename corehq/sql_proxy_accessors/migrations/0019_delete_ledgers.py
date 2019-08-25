# -*- coding: utf-8 -*-

from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0018_get_ledger_values_for_cases'),
    ]

    operations = [
        migrator.get_migration('delete_ledger_transactions_for_form.sql'),
        migrator.get_migration('delete_ledger_values.sql'),
    ]
