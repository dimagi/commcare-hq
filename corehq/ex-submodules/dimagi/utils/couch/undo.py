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
        return doc and doc['doc_type'].endswith(DELETED_SUFFIX)
    except KeyError:
        return False


def soft_delete(document):
    document.doc_type = get_deleted_doc_type(document)
    document.save()


def get_deleted_doc_type(document_class_or_instance):
    if isinstance(document_class_or_instance, Document):
        base_name = document_class_or_instance.doc_type
    else:
        base_name = document_class_or_instance.__name__
    return '{}{}'.format(base_name, DELETED_SUFFIX)


def undo_delete(document):
    if is_deleted(document):
        document.doc_type = removesuffix(document.doc_type, DELETED_SUFFIX)
        document.save()


def removesuffix(string: str, suffix: str) -> str:
    """
    If ``string`` ends with ``suffix``, returns ``string[:-len(suffix)]``,
    otherwise, returns ``string``.

    >>> 'Completed-Deleted'.rstrip(DELETED_SUFFIX)
    'Comp'
    >>> removesuffix('Completed-Deleted', DELETED_SUFFIX)
    'Completed'

    >>> 'I-Get-Deleted-But-I-Get-Undeleted-Again'.replace(DELETED_SUFFIX, '')
    'I-Get-But-I-Get-Undeleted-Again'
    >>> removesuffix('I-Get-Deleted-But-I-Get-Undeleted-Again', DELETED_SUFFIX)
    'I-Get-Deleted-But-I-Get-Undeleted-Again'

    """
    try:
        return string.removesuffix(suffix)  # Python 3.9+
    except AttributeError:
        if suffix and string.endswith(suffix):
            return string[:-len(suffix)]
        return string
