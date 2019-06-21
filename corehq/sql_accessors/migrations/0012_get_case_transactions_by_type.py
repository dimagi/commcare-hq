# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0011_get_case_types_for_domain'),
    ]

    operations = [
        migrator.get_migration('get_case_transactions_by_type.sql'),
        migrator.get_migration('get_case_transaction_by_form_id.sql'),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_case_transactions_for_rebuild(TEXT);",
            "SELECT 1"
        )
    ]
