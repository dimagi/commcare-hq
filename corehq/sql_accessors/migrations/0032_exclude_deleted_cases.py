# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.form_processor.models import CommCareCaseIndexSQL
from corehq.sql_db.operations import HqRunSQL, RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'RELATIONSHIP_TYPE_EXTENSION': CommCareCaseIndexSQL.EXTENSION
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0031_remove_get_ledger_values_for_product_ids'),
    ]

    operations = [
        migrator.get_migration('get_case_indices_reverse_2.sql'),
        migrator.get_migration('get_all_reverse_indices_1.sql'),
        migrator.get_migration('get_extension_case_ids_1.sql'),
    ]
