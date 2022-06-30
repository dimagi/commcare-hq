from django.db import migrations

from corehq.form_processor.models import XFormInstance, XFormOperation, CaseTransaction
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'FORM_STATE_ARCHIVED': XFormInstance.ARCHIVED,
    'FORM_STATE_NORMAL': XFormInstance.NORMAL,
    'FORM_OPERATION_ARCHIVE': XFormOperation.ARCHIVE,
    'FORM_OPERATION_UNARCHIVE': XFormOperation.UNARCHIVE,
    'TRANSACTION_TYPE_LEDGER': CaseTransaction.TYPE_LEDGER,
    'TRANSACTION_TYPE_FORM': CaseTransaction.TYPE_FORM,
})


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        # no longer required
        migrations.RunSQL(
            'DROP FUNCTION IF EXISTS deprecate_form(TEXT, TEXT, TIMESTAMP)',
            'SELECT 1'
        ),
        # replaced by save_new_form_and_related_models
        migrations.RunSQL(
            'DROP FUNCTION IF EXISTS save_new_form_with_attachments(form_processor_xforminstancesql, form_processor_xformattachmentsql[])',
            'SELECT 1'
        ),
        # signature changed
        migrations.RunSQL(
            """
            DROP FUNCTION IF EXISTS save_case_and_related_models(
                form_processor_commcarecasesql,
                form_processor_casetransaction[],
                form_processor_commcarecaseindexsql[],
                form_processor_caseattachmentsql[],
                INTEGER[],
                INTEGER[]
            )
            """,
            'SELECT 1'
        ),
        # signature changed
        migrations.RunSQL(
            """
            DROP FUNCTION IF EXISTS save_new_form_and_related_models(
            form_processor_xforminstancesql,
            form_processor_xformattachmentsql[],
            form_processor_xformoperationsql[]
            )
            """,
            'SELECT 1'
        ),
        # signature changed
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS revoke_restore_case_transactions_for_form(TEXT, BOOLEAN)",
            "SELECT 1",
        ),
        # replaced by delete_test_data
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_form_ids_in_domain(text, text);",
            "SELECT 1",
        ),
        migrator.get_migration('get_cases_by_id.sql'),
        migrator.get_migration('get_form_attachment_by_name.sql'),
        migrator.get_migration('get_forms_by_id.sql'),
        migrator.get_migration('get_forms_by_state.sql'),
        migrator.get_migration('get_multiple_cases_indices.sql'),
        migrator.get_migration('get_multiple_forms_attachments.sql'),
        migrator.get_migration('revoke_restore_case_transactions_for_form.sql'),
        migrator.get_migration('update_form_problem_and_state.sql'),
    ]
