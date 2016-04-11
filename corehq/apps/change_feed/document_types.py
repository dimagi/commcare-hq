from collections import namedtuple
from couchforms.models import all_known_formlike_doc_types
from dimagi.utils.couch.undo import DELETED_SUFFIX

CASE = 'case'
FORM = 'form'
META = 'meta'


DocumentType = namedtuple('DocumentType', ['raw_doc_type', 'primary_type', 'subtype', 'is_deletion'])


def get_doc_type_object_from_document(document):
    raw_doc_type = _get_document_type(document)
    if raw_doc_type:
        return DocumentType(
            raw_doc_type, get_primary_type(raw_doc_type), _get_document_subtype(document), _is_deletion(raw_doc_type)
        )


def get_primary_type(raw_doc_type):
    if raw_doc_type in ('CommCareCase', 'CommCareCase-Deleted'):
        return CASE
    elif raw_doc_type in all_known_formlike_doc_types():
        return FORM
    else:
        # at some point we may want to make this more granular
        return META


def _get_document_type(document_or_none):
    return document_or_none.get('doc_type', None) if document_or_none else None


def _get_document_subtype(document_or_none):
    type = _get_document_type(document_or_none)
    if type in ('CommCareCase', 'CommCareCase-Deleted'):
        return document_or_none.get('type', None)
    elif type in all_known_formlike_doc_types():
        return document_or_none.get('xmlns', None)
    return None

def _is_deletion(raw_doc_type):
    # can be overridden
    return raw_doc_type.endswith(DELETED_SUFFIX)
