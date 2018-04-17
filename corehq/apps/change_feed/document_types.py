from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.change_feed.exceptions import MissingMetaInformationError
from couchforms.models import all_known_formlike_doc_types
from dimagi.utils.couch.undo import DELETED_SUFFIX
from pillowtop.feed.interface import ChangeMeta

GROUP_DOC_TYPES = ('Group', 'Group-Deleted')

WEB_USER_DOC_TYPES = ('WebUser', 'WebUser-Deleted')

MOBILE_USER_DOC_TYPES = ('CommCareUser', 'CommCareUser-Deleted')

CASE_DOC_TYPES = ('CommCareCase', 'CommCareCase-Deleted')

DOMAIN_DOC_TYPES = ('Domain', 'Domain-Deleted', 'Domain-DUPLICATE')

SYNCLOG_DOC_TYPES = ('SyncLog', 'SimplifiedSyncLog')


def _get_document_type(document_or_none):
    return document_or_none.get('doc_type', None) if document_or_none else None


def _get_subtype(doc_type, document):
    if doc_type in ('CommCareCase', 'CommCareCase-Deleted'):
        return document.get('type', None)
    elif doc_type in all_known_formlike_doc_types():
        return document.get('xmlns', None)
    return None


def change_meta_from_doc(document):
    if document is None:
        raise MissingMetaInformationError('No document!')

    doc_id = document.get('_id', None)
    if not doc_id:
        raise MissingMetaInformationError("No doc ID!!")

    doc_type = _get_document_type(document)
    if not doc_type:
        raise MissingMetaInformationError("No doc_type: {}".format(doc_id))

    is_deletion_ = doc_type == 'Domain-DUPLICATE' or is_deletion(doc_type)
    return ChangeMeta(
        document_id=doc_id or document['_id'],
        document_rev=document.get('_rev', None),
        document_type=doc_type,
        document_subtype=_get_subtype(doc_type, document),
        domain=_get_domain(document),
        is_deletion=is_deletion_,
        backend_id=document.get('backend_id', None)
    )


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
    if document.get('doc_type', None) in DOMAIN_DOC_TYPES:
        return document.get('name')
    return document.get('domain', None)


def is_deletion(raw_doc_type):
    # can be overridden
    return raw_doc_type is not None and raw_doc_type.endswith(DELETED_SUFFIX)
