# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
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
        migrator.get_migration('get_form_ids_for_user.sql'),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS update_form_state(TEXT, INTEGER)",
            "SELECT 1"
        ),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_forms_by_user_id(TEXT, TEXT, INTEGER);",
            "SELECT 1"
        )
    ]
