from __future__ import absolute_import, unicode_literals

import six

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.preindex import get_preindex_plugin
from corehq.util.couch_helpers import paginate_view
from corehq.util.python_compatibility import soft_assert_type_text


def _get_all_docs_dbs():
    return get_preindex_plugin('couchapps').get_dbs('all_docs')


def get_all_doc_ids_for_domain_grouped_by_db(domain):
    """
    This function has the limitation that it only gets docs from dbs that are listed
    for couchapps 'all_docs' design doc in corehq/couchapps/__init__.py

    """
    for db in _get_all_docs_dbs():
        results = db.view(
            'by_domain_doc_type_date/view',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=False,
            reduce=False,
        )
        yield (db, (result['id'] for result in results))


def get_doc_count_by_type(db, doc_type):
    key = [doc_type]
    result = db.view(
        'all_docs/by_doc_type', startkey=key, endkey=key + [{}], reduce=True,
        group_level=1).one()
    if result:
        return result['value']
    else:
        return 0


def get_doc_count_by_domain_type(db, domain, doc_type):
    key = [domain, doc_type]
    result = db.view(
        'by_domain_doc_type_date/view', startkey=key, endkey=key + [{}], reduce=True,
        group_level=2).one()
    if result:
        return result['value']
    else:
        return 0


def get_all_docs_with_doc_types(db, doc_types):
    """
    doc_types must be a sequence of doc_types

    returns doc JSON (not wrapped)
    """
    if isinstance(doc_types, six.string_types):
        soft_assert_type_text(doc_types)
        raise TypeError('get_all_docs_with_doc_types requires doc_types '
                        'to be a sequence of strings, not {!r}'.format(doc_types))
    for doc_type in doc_types:
        results = paginate_view(
            db, 'all_docs/by_doc_type',
            chunk_size=100, startkey=[doc_type], endkey=[doc_type, {}],
            include_docs=True, reduce=False)
        for result in results:
            yield result['doc']


def get_doc_ids_by_class(doc_class):
    """Useful for migrations, but has the potential to be very large"""
    doc_type = doc_class.__name__
    return [row['id'] for row in doc_class.get_db().view(
        'all_docs/by_doc_type',
        startkey=[doc_type],
        endkey=[doc_type, {}],
        include_docs=False,
        reduce=False,
    )]


def get_deleted_doc_ids_by_class(doc_class):
    doc_type = doc_class.__name__ + DELETED_SUFFIX
    return [row['id'] for row in doc_class.get_db().view(
        'all_docs/by_doc_type',
        startkey=[doc_type],
        endkey=[doc_type, {}],
        include_docs=False,
        reduce=False,
    )]


def delete_all_docs_by_doc_type(db, doc_types):
    for chunk in chunked(get_all_docs_with_doc_types(db, doc_types), 100):
        db.bulk_delete(chunk)
