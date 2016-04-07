# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0015_get_form_ids_in_domain'),
    ]

    operations = [
        migrator.get_migration('get_ledger_values_for_product_ids.sql'),
    ]
