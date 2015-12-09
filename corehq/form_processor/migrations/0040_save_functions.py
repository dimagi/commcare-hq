# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.form_processor.utils.migration import migrate_sql_function


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0039_case_functions'),
    ]

    operations = [
        migrate_sql_function('save_new_form_with_attachments'),
        migrate_sql_function('deprecate_form'),
        migrate_sql_function('save_case_and_related_models'),
        migrate_sql_function('get_form_ids_in_domain'),
        migrate_sql_function('update_form_problem_and_state'),
    ]
