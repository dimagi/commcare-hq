# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0026_remove_get_ledger_values_for_product_ids'),
    ]

    operations = [
        migrator.get_migration('soft_undelete_cases.sql'),
        migrator.get_migration('soft_undelete_forms.sql'),
        migrator.get_migration('get_deleted_case_ids_by_owner.sql'),
    ]
