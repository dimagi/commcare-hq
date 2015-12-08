# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models, migrations

from corehq.util.migration import RawSQLMigration


migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunSQL(
            'CREATE EXTENSION IF NOT EXISTS plproxy',
            'DROP EXTENSION plproxy'
        ),
        migrations.RunSQL(
            'CREATE EXTENSION IF NOT EXISTS hashlib',
            'DROP EXTENSION hashlib'
        ),
        migrator.get_migration('archive_unarchive_form.sql'),
        migrator.get_migration('case_modified_since.sql'),
        migrator.get_migration('check_form_exists.sql'),
        migrator.get_migration('get_case_attachment_by_name.sql'),
        migrator.get_migration('get_case_attachments.sql'),
        migrator.get_migration('get_case_by_id.sql'),
        migrator.get_migration('get_case_by_location_id.sql'),
        migrator.get_migration('get_case_form_ids.sql'),
        migrator.get_migration('get_case_ids_in_domain.sql'),
        migrator.get_migration('get_case_indices.sql'),
        migrator.get_migration('get_case_indices_reverse.sql'),
        migrator.get_migration('get_case_transactions.sql'),
        migrator.get_migration('get_case_transactions_for_rebuild.sql'),
        migrator.get_migration('get_cases_by_id.sql'),
        migrator.get_migration('get_form_attachment_by_name.sql'),
        migrator.get_migration('get_form_attachments.sql'),
        migrator.get_migration('get_form_by_id.sql'),
        migrator.get_migration('get_form_ids_in_domain.sql'),
        migrator.get_migration('get_form_operations.sql'),
        migrator.get_migration('get_forms_by_id.sql'),
        migrator.get_migration('get_forms_by_state.sql'),
        migrator.get_migration('get_multiple_cases_indices.sql'),
        migrator.get_migration('get_multiple_forms_attachments.sql'),
        migrator.get_migration('get_reverse_indexed_cases.sql'),
        migrator.get_migration('hard_delete_cases.sql'),
        migrator.get_migration('hard_delete_forms.sql'),
        migrator.get_migration('revoke_restore_case_transactions_for_form.sql'),
        migrator.get_migration('save_case_and_related_models.sql'),
        migrator.get_migration('save_new_form_and_related_models.sql'),
        migrator.get_migration('update_form_problem_and_state.sql'),
    ]
