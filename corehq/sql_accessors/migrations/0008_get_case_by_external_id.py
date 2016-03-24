# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0007_rename_get_case_attachment_by_name'),
    ]

    operations = [
        migrator.get_migration('get_case_by_external_id.sql'),
    ]
