# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0006_add_fields_to_case_attachments'),
    ]

    operations = [
        HqRunSQL(
            "DROP FUNCTION IF EXISTS get_case_attachment_by_name(TEXT, TEXT)",
            "SELECT 1"
        ),
        migrator.get_migration('get_case_attachment_by_identifier.sql'),
    ]
