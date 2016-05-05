# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0020_soft_delete_cases'),
    ]

    operations = [
        HqRunSQL(
            "DROP FUNCTION IF EXISTS get_ledger_values_for_case(TEXT)",
            "SELECT 1"
        ),
        migrator.get_migration('get_ledger_values_for_cases.sql'),
    ]
