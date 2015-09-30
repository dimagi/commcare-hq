from corehq.preindex import get_preindex_plugin
from dimagi.utils.couch.database import get_db


def _get_all_docs_dbs():
    return get_preindex_plugin('domain').get_dbs('domain') + [get_db(None)]


def get_all_doc_ids_for_domain_grouped_by_db(domain):
    """
    This function has the limitation that it only gets docs from the main db
    and extra dbs that are listed for the 'domain' design doc
    in corehq/apps/domain/__init__.py

    """
    # todo: move view to all_docs/by_domain_doc_type as in this original commit:
    # todo: https://github.com/dimagi/commcare-hq/commit/400d3878afc5e9f5118ffb30d22b8cebe9afb4a6
    for db in _get_all_docs_dbs():
        results = db.view(
            'domain/related_to_domain',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=False,
            reduce=False,
        )
        yield (db, (result['id'] for result in results))
