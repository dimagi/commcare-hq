# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0039_update_reindex_queries'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_all_cases_modified_since(timestamp with time zone, integer)",
            "SELECT 1"
        ),
    ]
