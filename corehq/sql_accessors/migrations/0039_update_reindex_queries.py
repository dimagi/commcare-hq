# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0038_save_case_deletion_fields'),
    ]

    operations = [
        migrator.get_migration('get_all_forms_received_since_2.sql'),
        migrator.get_migration('get_all_ledger_values_modified_since_2.sql'),
    ]
