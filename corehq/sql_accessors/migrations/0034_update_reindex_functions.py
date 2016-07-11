# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0033_remove_location_id_from_ledgers'),
    ]

    operations = [
        migrator.get_migration('get_all_cases_modified_since_1.sql'),
        migrator.get_migration('get_all_forms_received_since_1.sql'),
        migrator.get_migration('get_all_ledger_values_modified_since_1.sql'),
    ]
