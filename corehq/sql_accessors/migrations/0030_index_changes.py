# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.form_processor.models import CaseTransaction
from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'TRANSACTION_TYPE_FORM': CaseTransaction.TYPE_FORM
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0029_get_case_ids_in_domain'),
    ]

    operations = [
        HqRunSQL(
            "DROP FUNCTION IF EXISTS get_case_indices_reverse(TEXT);",
            "SELECT 1"
        ),
        HqRunSQL(
            "DROP FUNCTION IF EXISTS get_case_indices(TEXT);",
            "SELECT 1"
        ),
        migrator.get_migration('get_case_indices_1.sql'),
        migrator.get_migration('hard_delete_cases_1.sql'),
    ]
