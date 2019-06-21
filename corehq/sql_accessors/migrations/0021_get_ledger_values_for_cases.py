# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0020_soft_delete_cases'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_ledger_values_for_case(TEXT)",
            "SELECT 1"
        ),
        migrator.get_migration('get_ledger_values_for_cases.sql'),
    ]
