# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration
from corehq.form_processor.models import XFormInstanceSQL

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'FORM_STATE_DELETED': XFormInstanceSQL.DELETED
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0034_update_reindex_functions'),
    ]

    operations = [
        migrator.get_migration('soft_undelete_cases.sql'),
        migrator.get_migration('soft_undelete_forms.sql'),
        migrator.get_migration('get_deleted_case_ids_by_owner.sql'),
    ]
