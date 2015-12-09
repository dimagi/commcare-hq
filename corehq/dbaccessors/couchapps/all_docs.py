from corehq.preindex import get_preindex_plugin
from corehq.util.couch_helpers import paginate_view
from dimagi.utils.chunked import chunked


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


def get_all_docs_with_doc_types(db, doc_types):
    for doc_type in doc_types:
        results = paginate_view(
            db, 'all_docs/by_doc_type',
            chunk_size=100, startkey=[doc_type], endkey=[doc_type, {}],
            include_docs=True, reduce=False)
        for result in results:
            yield result['doc']


def delete_all_docs_by_doc_type(db, doc_types):
    for chunk in chunked(get_all_docs_with_doc_types(db, doc_types), 100):
        db.bulk_delete(chunk)
