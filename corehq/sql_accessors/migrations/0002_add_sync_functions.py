# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.form_processor.models import XFormInstanceSQL, XFormOperationSQL, CaseTransaction, \
    CommCareCaseIndexSQL
from corehq.sql_db.operations import HqRunSQL, RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'RELATIONSHIP_TYPE_EXTENSION': CommCareCaseIndexSQL.EXTENSION
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0001_initial')
    ]

    operations = [
        migrator.get_migration('get_case_ids_in_domain_by_owners.sql'),
        migrator.get_migration('get_open_case_ids.sql'),
        migrator.get_migration('get_closed_case_ids.sql'),
        migrator.get_migration('get_last_modified_dates.sql'),
        migrator.get_migration('get_indexed_case_ids.sql'),
        migrator.get_migration('get_extension_case_ids.sql'),
        migrator.get_migration('case_has_transactions_since_sync.sql'),
        migrator.get_migration('get_all_reverse_indices.sql'),
    ]
