# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0067_livequery_sql_include_deleted_indices'),
    ]

    operations = [
        migrator.get_migration('get_form_ids_for_user_2.sql'),
        migrator.get_migration('soft_delete_forms_3.sql'),
        migrator.get_migration('soft_undelete_forms_3.sql'),
    ]
