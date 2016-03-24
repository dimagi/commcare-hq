# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0008_get_case_by_external_id'),
    ]

    operations = [
        migrator.get_migration('get_ledger_values_for_case.sql'),
        migrator.get_migration('get_ledger_value.sql'),
        migrator.get_migration('save_ledger_values.sql'),
    ]
