from datetime import datetime
from couchdbkit.ext.django.schema import *

DELETED_SUFFIX = '-Deleted'

class DeleteRecord(Document):
    base_doc = 'DeleteRecord'
    domain = StringProperty()
    datetime = DateTimeProperty()

class DeleteDocRecord(DeleteRecord):
    doc_id = StringProperty()

    def undo(self):
        doc = self.get_doc()
        doc.doc_type = doc.doc_type.rstrip(DELETED_SUFFIX)
        doc.save()

class UndoableDocument(Document):
    def soft_delete(self, domain_included=True):
        if not self.doc_type.endswith(DELETED_SUFFIX):
            self.doc_type += DELETED_SUFFIX
            try:
                domain = self.domain
            except Exception:
                domain = None
            extra_args = {}
            if domain_included:
                extra_args["domain"] = self.domain

            record = self.create_delete_record(
                doc_id=self.get_id,
                datetime=datetime.utcnow(),
                **extra_args
            )
            record.save()
            self.save()
            return record