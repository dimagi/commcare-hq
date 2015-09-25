from corehq.preindex import get_preindex_plugin


def _get_all_docs_dbs():
    return get_preindex_plugin('couchapps').get_dbs('all_docs')


def get_all_doc_ids_for_domain_grouped_by_db(domain):
    for db in _get_all_docs_dbs():
        results = db.view(
            'all_docs/by_domain_doc_type',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=False,
            reduce=False,
        )
        yield (db, (result['id'] for result in results))
