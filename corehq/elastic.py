from pillowtop.processors.elastic import send_to_elasticsearch as send_to_es

from corehq.apps.es.client import get_client, manager
from corehq.apps.es.exceptions import ESError  # noqa: F401
from corehq.apps.es.transient_util import (  # noqa: F401
    index_info_from_cname,
    doc_adapter_from_cname,
    doc_adapter_from_info,
    report_and_fail_on_shard_failures,
)
from corehq.util.files import TransientTempfile


def get_es_new():
    # TODO: remove this (update where imported)
    return get_client()


def get_es_export():
    # TODO: remove this (update where imported)
    return get_client(for_export=True)


def doc_exists_in_es(index_info, doc_id):
    """
    Check if a document exists
    """
    return doc_adapter_from_info(index_info).exists(doc_id)


def send_to_elasticsearch(index_cname, doc, delete=False, es_merge_update=False):
    """
    Utility method to update the doc in elasticsearch.
    Duplicates the functionality of pillowtop but can be called directly.
    """
    doc_id = doc['_id']
    if isinstance(doc_id, bytes):
        doc_id = doc_id.decode('utf-8')
    index_info = index_info_from_cname(index_cname)
    return send_to_es(
        index_info=index_info,
        doc_type=index_info.type,
        doc_id=doc_id,
        es_getter=get_client,
        name="{}.{} <{}>:".format(send_to_elasticsearch.__module__,
                                  send_to_elasticsearch.__name__, index_cname),
        data=doc,
        delete=delete,
        es_merge_update=es_merge_update,
    )


def refresh_elasticsearch_index(index_cname):
    manager.index_refresh(doc_adapter_from_cname(index_cname).index_name)


def _iter_es_docs(index_cname, ids):
    """Returns a generator which pulls documents from elasticsearch in chunks"""
    adapter = doc_adapter_from_cname(index_cname)
    yield from adapter.iter_docs(ids)


def iter_es_docs_from_query(query):
    """Returns all docs which match query"""
    scroll_result = query.scroll_ids()

    def iter_export_docs():
        with TransientTempfile() as temp_path:
            with open(temp_path, 'w', encoding='utf-8') as f:
                for doc_id in scroll_result:
                    f.write(doc_id + '\n')

            # Stream doc ids from disk and fetch documents from ES in chunks
            with open(temp_path, 'r', encoding='utf-8') as f:
                doc_ids = (doc_id.strip() for doc_id in f)
                for doc in _iter_es_docs(query.index, doc_ids):
                    yield doc

    return ScanResult(query.count(), iter_export_docs())


class ScanResult(object):

    def __init__(self, count, iterator):
        self._iterator = iterator
        self.count = count

    def __iter__(self):
        for x in self._iterator:
            yield x
