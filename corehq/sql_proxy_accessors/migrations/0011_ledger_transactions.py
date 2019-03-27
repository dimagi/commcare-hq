# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0010_merge'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS save_ledger_values(TEXT[], form_processor_ledgervalue[]);",
            "SELECT 1"
        ),
        migrator.get_migration('get_ledger_transactions_for_case.sql'),
    ]
