# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0010_update_state_type_values'),
    ]

    operations = [
        migrator.get_migration('get_case_types_for_domain.sql'),
    ]
