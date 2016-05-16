# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'FORM_STATE_DELETED': XFormInstanceSQL.DELETED
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0014_ledger_transactions'),
    ]

    operations = [
        migrator.get_migration('get_ledger_transactions_for_case.sql'),
        migrator.get_migration('get_latest_ledger_transaction.sql'),
        migrator.get_migration('save_ledger_values.sql'),
    ]
