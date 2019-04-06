# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0035_add_undelete_functions'),
    ]

    operations = [
        migrator.get_migration('get_case_by_location_id_1.sql'),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_case_ids_in_domain(TEXT, TEXT, TEXT[], BOOLEAN)",
            "SELECT 1"
        ),
        migrator.get_migration('get_case_ids_in_domain_2.sql'),
        migrator.get_migration('get_case_ids_modified_with_owner_since_1.sql'),
        migrator.get_migration('get_case_by_external_id_1.sql'),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_deleted_case_ids_by_owner(TEXT, TEXT)",
            "SELECT 1"
        )
    ]
