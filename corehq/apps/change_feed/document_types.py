from collections import namedtuple

from corehq.apps.change_feed.exceptions import MissingMetaInformationError
from couchforms.models import all_known_formlike_doc_types
from dimagi.utils.couch.undo import DELETED_SUFFIX
from pillowtop.feed.interface import ChangeMeta

GROUP_DOC_TYPES = ('Group', 'Group-Deleted')
WEB_USER_DOC_TYPES = ('WebUser', 'WebUser-Deleted')
MOBILE_USER_DOC_TYPES = ('CommCareUser', 'CommCareUser-Deleted')
DOMAIN_DOC_TYPES = ('Domain', 'Domain-Deleted', 'Domain-DUPLICATE')
CASE_DOC_TYPES = ('CommCareCase', 'CommCareCase-Deleted')
SYNCLOG_DOC_TYPES = ('SyncLog', 'SimplifiedSyncLog')


DocumentMetadata = namedtuple(
    'DocumentMetadata', ['raw_doc_type', 'subtype', 'domain', 'is_deletion']
)


def get_doc_meta_object_from_document(document):
    raw_doc_type = _get_document_type(document)
    if raw_doc_type:
        return _make_document_type(raw_doc_type, document)


def _make_document_type(raw_doc_type, document):
    if raw_doc_type in CASE_DOC_TYPES:
        return _case_doc_type_constructor(raw_doc_type, document)
    elif raw_doc_type in all_known_formlike_doc_types():
        return _form_doc_type_constructor(raw_doc_type, document)
    elif raw_doc_type in DOMAIN_DOC_TYPES:
        return _domain_doc_type_constructor(raw_doc_type, document)
    else:
        return DocumentMetadata(
            raw_doc_type, None, _get_domain(document), is_deletion(raw_doc_type)
        )


def _get_document_type(document_or_none):
    return document_or_none.get('doc_type', None) if document_or_none else None


def _case_doc_type_constructor(raw_doc_type, document):
    return DocumentMetadata(
        raw_doc_type, document.get('type', None), _get_domain(document), is_deletion(raw_doc_type)
    )


def _form_doc_type_constructor(raw_doc_type, document):
    return DocumentMetadata(
        raw_doc_type, document.get('xmlns', None), _get_domain(document), is_deletion(raw_doc_type)
    )


def _domain_doc_type_constructor(raw_doc_type, document):
    is_deletion_ = raw_doc_type == 'Domain-DUPLICATE' or is_deletion(raw_doc_type)
    return DocumentMetadata(
        raw_doc_type, None, document.get('name', None), is_deletion_
    )


def change_meta_from_doc(document, data_source_type, data_source_name):
    if document is None:
        raise MissingMetaInformationError('No document!')

    doc_meta = get_doc_meta_object_from_document(document)
    return change_meta_from_doc_meta_and_document(doc_meta, document, data_source_type, data_source_name)


def change_meta_from_doc_meta_and_document(doc_meta, document, data_source_type, data_source_name, doc_id=None):
    if doc_meta is None:
        raise MissingMetaInformationError("Couldn't guess document type for {}!".format(document))

    doc_id = doc_id or document.get('_id', None)
    if not doc_id:
        raise MissingMetaInformationError("No doc ID for {}".format(document))
    return ChangeMeta(
        document_id=doc_id or document['_id'],
        document_rev=document.get('_rev', None),
        data_source_type=data_source_type,
        data_source_name=data_source_name,
        document_type=doc_meta.raw_doc_type,
        document_subtype=doc_meta.subtype,
        domain=doc_meta.domain,
        is_deletion=doc_meta.is_deletion,
    )


def _get_domain(document):
    return document.get('domain', None)


def is_deletion(raw_doc_type):
    # can be overridden
    return raw_doc_type is not None and raw_doc_type.endswith(DELETED_SUFFIX)
