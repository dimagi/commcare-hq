from django.apps import AppConfig


class FormProcessorAppConfig(AppConfig):
    name = 'corehq.form_processor'

    def ready(self):
        from psycopg2.extensions import register_adapter
        from corehq.form_processor.utils.sql import form_adapter, formattachment_adapter

        XFormInstanceSQL = self.get_model('XFormInstanceSQL')
        XFormAttachmentSQL = self.get_model('XFormAttachmentSQL')
        register_adapter(XFormInstanceSQL, form_adapter)
        register_adapter(XFormAttachmentSQL, formattachment_adapter)
