# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.form_processor.utils.migration import migrate_sql_function


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0039_auto_20151130_1748'),
    ]

    operations = [
        migrate_sql_function('get_case_by_id'),
        migrate_sql_function('get_cases_by_id'),
        migrate_sql_function('case_modified_since'),
        migrate_sql_function('get_case_form_ids'),
        migrate_sql_function('get_case_indices'),
        migrate_sql_function('get_case_indices_reverse'),
        migrate_sql_function('get_reverse_indexed_cases'),
        migrate_sql_function('get_multiple_cases_indices'),
        migrate_sql_function('hard_delete_cases'),
        migrations.RunSQL('DROP FUNCTION IF EXISTS hard_delete_forms(text[]);'),  # delete old one
        migrate_sql_function('hard_delete_forms'),  # updated
        migrate_sql_function('get_case_attachment_by_name'),
        migrate_sql_function('get_case_attachments'),
        migrate_sql_function('get_case_transactions'),
        migrate_sql_function('get_case_transactions_for_rebuild'),
        migrate_sql_function('get_case_by_location_id'),
        migrate_sql_function('get_case_ids_in_domain'),
    ]
