# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0008_get_case_by_external_id'),
    ]

    operations = [
        migrator.get_migration('get_ledger_value.sql'),
    ]
