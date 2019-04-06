# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.form_processor.models import CaseTransaction
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'TRANSACTION_TYPE_FORM': CaseTransaction.TYPE_FORM
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0029_get_case_ids_in_domain'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_case_indices_reverse(TEXT);",
            "SELECT 1"
        ),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_case_indices(TEXT);",
            "SELECT 1"
        ),
        migrator.get_migration('get_case_indices_1.sql'),
    ]
