# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0045_drop_case_modified_since'),
    ]

    operations = [
        migrator.get_migration('get_form_ids_by_type_and_date.sql'),
    ]
