from django.apps import AppConfig


class FormProcessorAppConfig(AppConfig):
    name = 'corehq.form_processor'

    def ready(self):
        from corehq.form_processor import tasks  # noqa
        from psycopg2.extensions import register_adapter
        from corehq.form_processor.utils.sql import (
            form_adapter, form_operation_adapter,
            case_adapter, case_attachment_adapter, case_index_adapter, case_transaction_adapter,
            ledger_value_adapter, ledger_transaction_adapter
        )

        XFormInstance = self.get_model('XFormInstance')
        XFormOperation = self.get_model('XFormOperation')
        register_adapter(XFormInstance, form_adapter)
        register_adapter(XFormOperation, form_operation_adapter)

        CommCareCase = self.get_model('CommCareCase')
        CaseTransaction = self.get_model('CaseTransaction')
        CommCareCaseIndexSQL = self.get_model('CommCareCaseIndexSQL')
        CaseAttachment = self.get_model('CaseAttachment')
        register_adapter(CommCareCase, case_adapter)
        register_adapter(CaseTransaction, case_transaction_adapter)
        register_adapter(CommCareCaseIndexSQL, case_index_adapter)
        register_adapter(CaseAttachment, case_attachment_adapter)

        LedgerValue = self.get_model('LedgerValue')
        LedgerTransaction = self.get_model('LedgerTransaction')
        register_adapter(LedgerValue, ledger_value_adapter)
        register_adapter(LedgerTransaction, ledger_transaction_adapter)
