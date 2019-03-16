# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations
from django.conf import settings

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0008_get_case_types_for_domain'),
    ]

    operations = [
        migrator.get_migration('get_case_transactions_by_type.sql'),
        migrator.get_migration('get_case_transaction_by_form_id.sql'),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_case_transactions_for_rebuild(TEXT);",
            "SELECT 1"
        )
    ]
