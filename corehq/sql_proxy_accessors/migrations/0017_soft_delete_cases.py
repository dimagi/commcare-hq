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
        ('sql_proxy_accessors', '0016_get_case_ids_in_domain_by_owners'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS soft_delete_cases(TEXT, TEXT[], TIMESTAMP, TEXT)",
            "SELECT 1"
        ),
        migrator.get_migration('soft_delete_cases.sql'),
    ]
