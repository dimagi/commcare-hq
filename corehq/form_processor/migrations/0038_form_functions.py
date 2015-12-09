# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.form_processor.utils.migration import migrate_sql_function


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0037_get_form_by_id_fn'),
    ]

    operations = [
        migrate_sql_function('get_form_by_id'),
        migrate_sql_function('get_form_attachments'),
        migrate_sql_function('get_form_attachment_by_name'),
        migrate_sql_function('get_forms_by_id'),
        migrate_sql_function('get_form_operations'),
        migrate_sql_function('get_multiple_forms_attachments'),
        migrate_sql_function('get_forms_by_state'),
        migrate_sql_function('check_form_exists'),
        migrate_sql_function('hard_delete_forms'),
        migrate_sql_function('archive_unarchive_form'),
        migrate_sql_function('revoke_restore_case_transactions_for_form'),
    ]
