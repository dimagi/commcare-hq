# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0021_get_all_ledger_values_modified_since'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_all_reverse_indices(TEXT[])",
            "SELECT 1"
        ),
        migrator.get_migration('get_all_reverse_indices.sql'),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_case_form_ids(TEXT)",
            "SELECT 1"
        ),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_closed_case_ids(text, text)",
            "SELECT 1"
        ),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_indexed_case_ids(TEXT, TEXT[]);",
            "SELECT 1"
        ),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_multiple_cases_indices(TEXT[]);",
            "SELECT 1"
        ),
        migrator.get_migration('get_multiple_cases_indices.sql'),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_mulitple_forms_attachments(TEXT[])",
            "SELECT 1"
        ),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_form_by_id(TEXT);",
            "SELECT 1"
        )
    ]
