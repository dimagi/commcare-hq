from dimagi.utils.dates import force_to_datetime

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.blobs import get_blob_db
from corehq.blobs.mixin import BlobMetaRef


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(self):
        return 'InvoicePdf'

    @classmethod
    def sql_class(self):
        from corehq.apps.accounting.models import SQLInvoicePdf
        return SQLInvoicePdf

    @classmethod
    def commit_adding_migration(cls):
        return "TODO after merge"

    def update_or_create_sql_object(self, doc):
        db = get_blob_db()
        blob_key = None
        doc_blobs = doc.get('external_blobs', {})
        if len(doc_blobs):
            blob_data = doc_blobs[list(doc_blobs)[0]]   # InvoicePdfs have at most one blob
            blob_key = BlobMetaRef._normalize_json('commcarehq', doc['_id'], blob_data)['key']
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={
                "invoice_id": doc.get('invoice_id'),
                "date_created": force_to_datetime(doc.get('date_created')),
                "is_wire": doc.get('is_wire', False),
                "is_customer": doc.get('is_customer', False),
                "blob_key": blob_key,
            })
        return (model, created)
