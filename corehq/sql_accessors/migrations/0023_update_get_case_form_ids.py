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
        ('sql_accessors', '0022_last_modified_form_id'),
    ]

    operations = [
        migrator.get_migration('get_case_form_ids.sql'),
    ]
