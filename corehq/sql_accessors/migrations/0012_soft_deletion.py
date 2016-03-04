# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'FORM_STATE_DELETED': XFormInstanceSQL.DELETED
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0011_get_case_types_for_domain'),
    ]

    operations = [
        migrator.get_migration('soft_delete_cases.sql'),
        migrator.get_migration('soft_undelete_cases.sql'),
        migrator.get_migration('soft_delete_forms.sql'),
        migrator.get_migration('soft_undelete_forms.sql'),
    ]
