# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.form_processor.models import XFormInstanceSQL, XFormOperationSQL, CaseTransaction, \
    CommCareCaseIndexSQL
from corehq.sql_db.operations import HqRunSQL, RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0018_save_ledger_values_rebuild')
    ]

    operations = [
        migrator.get_migration('get_case_ids_in_domain_by_owners.sql'),
    ]
