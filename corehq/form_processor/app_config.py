from django.apps import AppConfig


class FormProcessorAppConfig(AppConfig):
    name = 'corehq.form_processor'

    def ready(self):
        from psycopg2.extensions import register_adapter
        from corehq.form_processor.utils.sql import (
            form_adapter, form_attachment_adapter,
            case_adapter, case_attachment_adapter, case_index_adapter, case_transaction_adapter
        )

        XFormInstanceSQL = self.get_model('XFormInstanceSQL')
        XFormAttachmentSQL = self.get_model('XFormAttachmentSQL')
        register_adapter(XFormInstanceSQL, form_adapter)
        register_adapter(XFormAttachmentSQL, form_attachment_adapter)

        CommCareCaseSQL = self.get_model('CommCareCaseSQL')
        CaseTransaction = self.get_model('CaseTransaction')
        CommCareCaseIndexSQL = self.get_model('CommCareCaseIndexSQL')
        CaseAttachmentSQL = self.get_model('CaseAttachmentSQL')
        register_adapter(CommCareCaseSQL, case_adapter)
        register_adapter(CaseTransaction, case_transaction_adapter)
        register_adapter(CommCareCaseIndexSQL, case_index_adapter)
        register_adapter(CaseAttachmentSQL, case_attachment_adapter)
