# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0019_get_case_ids_in_domain_by_owners'),
    ]

    operations = [
        HqRunSQL(
            "DROP FUNCTION IF EXISTS soft_delete_cases(TEXT, TEXT[], TIMESTAMP, TEXT)",
            "SELECT 1"
        ),
        migrator.get_migration('soft_delete_cases.sql'),
    ]
