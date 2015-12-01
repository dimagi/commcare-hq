# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.form_processor.utils.migration import migrate_sql_function


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0038_form_functions'),
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
    ]
