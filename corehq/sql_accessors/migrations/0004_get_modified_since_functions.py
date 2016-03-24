# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration


migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0003_get_forms_by_user_id_functions')
    ]

    operations = [
        migrator.get_migration('get_all_cases_modified_since.sql'),
        migrator.get_migration('get_all_forms_received_since.sql'),
    ]
