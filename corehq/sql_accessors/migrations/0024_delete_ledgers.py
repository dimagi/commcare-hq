# -*- coding: utf-8 -*-

from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0023_update_get_case_form_ids'),
    ]

    operations = [
        migrator.get_migration('delete_ledger_transactions_for_form.sql'),
        migrator.get_migration('delete_ledger_values.sql'),
    ]
