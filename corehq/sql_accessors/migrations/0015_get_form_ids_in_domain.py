# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.sql_db.operations import RawSQLMigration


migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0014_ledger_transactions'),
    ]

    operations = [
        migrator.get_migration('get_form_ids_in_domain_by_type.sql'),
    ]
