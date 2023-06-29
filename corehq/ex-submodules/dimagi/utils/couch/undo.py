from datetime import datetime
from dimagi.ext.couchdbkit import DateTimeProperty, Document, StringProperty

from corehq.apps.cleanup.models import DeletedCouchDoc

DELETED_SUFFIX = '-Deleted'


class DeleteRecord(Document):
    base_doc = 'DeleteRecord'
    domain = StringProperty()
    datetime = DateTimeProperty()


class DeleteDocRecord(DeleteRecord):
    doc_id = StringProperty()

    def undo(self):
        doc = self.get_doc()
        undo_delete(doc)


class UndoableDocument(Document):
    def soft_delete(self, domain_included=True):
        if not self.doc_type.endswith(DELETED_SUFFIX):
            self.doc_type = get_deleted_doc_type(self)
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
        return doc and _is_doc_type_deleted(doc['doc_type'])
    except KeyError:
        return False


def _is_doc_type_deleted(doc_type):
    return doc_type.endswith(DELETED_SUFFIX)


def soft_delete(document):
    document.doc_type = get_deleted_doc_type(document)
    document.save()


def get_deleted_doc_type(document_class_or_instance):
    if isinstance(document_class_or_instance, Document):
        base_name = document_class_or_instance.doc_type
    else:
        base_name = document_class_or_instance.__name__
    return '{}{}'.format(base_name, DELETED_SUFFIX)


def undo_delete(document, save=True):
    DeletedCouchDoc.objects.filter(
        doc_type=document['doc_type'],
        doc_id=document['_id'],
    ).delete()
    document.doc_type = remove_deleted_doc_type_suffix(document['doc_type'])
    if save:
        document.save()


def remove_deleted_doc_type_suffix(doc_type):
    while _is_doc_type_deleted(doc_type):
        doc_type = doc_type.removesuffix(DELETED_SUFFIX)
    return doc_type
