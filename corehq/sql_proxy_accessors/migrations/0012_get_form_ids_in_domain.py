# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models, migrations
from corehq.sql_db.operations import RawSQLMigration


migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})

class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0011_ledger_transactions'),
    ]

    operations = [
        migrator.get_migration('get_form_ids_in_domain_by_type.sql'),
    ]
