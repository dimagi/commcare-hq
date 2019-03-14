# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'FORM_STATE_DELETED': XFormInstanceSQL.DELETED
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0013_merge'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS save_ledger_values(TEXT[], form_processor_ledgervalue[]);",
            "SELECT 1"
        ),
        migrator.get_migration('get_ledger_transactions_for_case.sql'),
    ]
