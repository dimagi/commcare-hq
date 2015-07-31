from datetime import datetime
from dimagi.ext.couchdbkit import *

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


def is_deleted(doc):
    """
    Return True if a document was deleted via the UndoableDocument.soft_delete mechanism.

    Returns False otherwise.
    """
    try:
        return doc and doc['doc_type'].endswith(DELETED_SUFFIX)
    except KeyError:
        return False
