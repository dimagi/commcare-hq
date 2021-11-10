import json

from django.conf import settings

from memoized import memoized

from dimagi.utils.chunked import chunked
from pillowtop.processors.elastic import send_to_elasticsearch as send_to_es

from corehq.apps.es.exceptions import ESError
from corehq.apps.es.registry import registry_entry
from corehq.util.es.elasticsearch import (
    Elasticsearch,
    ElasticsearchException,
    SerializationError,
)
from corehq.util.es.interface import ElasticsearchInterface
from corehq.util.files import TransientTempfile
from corehq.util.json import CommCareJSONEncoder
from corehq.util.metrics import metrics_counter


class ESJSONSerializer(object):
    """Modfied version of ``elasticsearch.serializer.JSONSerializer``
    that uses the CommCareJSONEncoder for serializing to JSON.
    """
    mimetype = 'application/json'

    def loads(self, s):
        try:
            return json.loads(s)
        except (ValueError, TypeError) as e:
            raise SerializationError(s, e)

    def dumps(self, data):
        # don't serialize strings
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, cls=CommCareJSONEncoder)
        except (ValueError, TypeError) as e:
            raise SerializationError(data, e)


def _es_hosts():
    es_hosts = getattr(settings, 'ELASTICSEARCH_HOSTS', None)
    if not es_hosts:
        es_hosts = [settings.ELASTICSEARCH_HOST]

    hosts = [
        {
            'host': host,
            'port': settings.ELASTICSEARCH_PORT,
        }
        for host in es_hosts
    ]
    return hosts


@memoized
def get_es_new():
    """
    Get a handle to the configured elastic search DB.
    Returns an elasticsearch.Elasticsearch instance.
    """
    hosts = _es_hosts()
    es = Elasticsearch(hosts, timeout=settings.ES_SEARCH_TIMEOUT, serializer=ESJSONSerializer())
    return es


@memoized
def get_es_export():
    """
    Get a handle to the configured elastic search DB with settings geared towards exports.
    Returns an elasticsearch.Elasticsearch instance.
    """
    hosts = _es_hosts()
    es = Elasticsearch(
        hosts,
        retry_on_timeout=True,
        max_retries=3,
        # Timeout in seconds for an elasticsearch query
        timeout=300,
        serializer=ESJSONSerializer(),
    )
    return es


ES_DEFAULT_INSTANCE = 'default'
ES_EXPORT_INSTANCE = 'export'

ES_INSTANCES = {
    ES_DEFAULT_INSTANCE: get_es_new,
    ES_EXPORT_INSTANCE: get_es_export,
}


def get_es_instance(es_instance_alias=ES_DEFAULT_INSTANCE):
    assert es_instance_alias in ES_INSTANCES
    return ES_INSTANCES[es_instance_alias]()


def doc_exists_in_es(index_info, doc_id):
    """
    Check if a document exists
    """
    return ElasticsearchInterface(get_es_new()).doc_exists(index_info.alias, doc_id, index_info.type)


def send_to_elasticsearch(index_cname, doc, delete=False, es_merge_update=False):
    """
    Utility method to update the doc in elasticsearch.
    Duplicates the functionality of pillowtop but can be called directly.
    """
    doc_id = doc['_id']
    if isinstance(doc_id, bytes):
        doc_id = doc_id.decode('utf-8')
    index_info = registry_entry(index_cname)
    return send_to_es(
        index_info=index_info,
        doc_type=index_info.type,
        doc_id=doc_id,
        es_getter=get_es_new,
        name="{}.{} <{}>:".format(send_to_elasticsearch.__module__,
                                  send_to_elasticsearch.__name__, index_cname),
        data=doc,
        delete=delete,
        es_merge_update=es_merge_update,
    )


def refresh_elasticsearch_index(index_cname):
    index_info = registry_entry(index_cname)
    es = get_es_new()
    es.indices.refresh(index=index_info.alias)


# this is what ES's maxClauseCount is currently set to, can change this config
# value if we want to support querying over more domains
ES_MAX_CLAUSE_COUNT = 1024


class ESShardFailure(ESError):
    pass


def run_query(index_cname, q, debug_host=None, es_instance_alias=ES_DEFAULT_INSTANCE):
    # the debug_host parameter allows you to query another env for testing purposes
    if debug_host:
        if not settings.DEBUG:
            raise Exception("You can only specify an ES env in DEBUG mode")
        es_host = settings.ELASTICSEARCH_DEBUG_HOSTS[debug_host]
        es_instance = Elasticsearch([{'host': es_host,
                                      'port': settings.ELASTICSEARCH_PORT}],
                                    timeout=3, max_retries=0)
    else:
        es_instance = get_es_instance(es_instance_alias)

    es_interface = ElasticsearchInterface(es_instance)

    index_info = registry_entry(index_cname)
    try:
        results = es_interface.search(index_info.alias, index_info.type, body=q)
        report_and_fail_on_shard_failures(results)
        return results
    except ElasticsearchException as e:
        raise ESError(e)


def mget_query(index_cname, ids):
    if not ids:
        return []

    es_interface = ElasticsearchInterface(get_es_new())
    index_info = registry_entry(index_cname)
    try:
        return es_interface.get_bulk_docs(index_info.alias, index_info.type, ids)
    except ElasticsearchException as e:
        raise ESError(e)


def iter_es_docs(index_cname, ids):
    """Returns a generator which pulls documents from elasticsearch in chunks"""
    for ids_chunk in chunked(ids, 100):
        yield from mget_query(index_cname, ids_chunk)


def iter_es_docs_from_query(query):
    """Returns all docs which match query
    """
    scroll_result = query.scroll_ids()

    def iter_export_docs():
        with TransientTempfile() as temp_path:
            with open(temp_path, 'w', encoding='utf-8') as f:
                for doc_id in scroll_result:
                    f.write(doc_id + '\n')

            # Stream doc ids from disk and fetch documents from ES in chunks
            with open(temp_path, 'r', encoding='utf-8') as f:
                doc_ids = (doc_id.strip() for doc_id in f)
                for doc in iter_es_docs(query.index, doc_ids):
                    yield doc

    return ScanResult(query.count(), iter_export_docs())


def scroll_query(index_cname, query, es_instance_alias=ES_DEFAULT_INSTANCE, **kw):
    """Perfrom a scrolling search, yielding each doc until the entire context
    is exhausted.

    :param index_cname: Canonical (registered) name of index to search.
    :param query: Dict, raw search query.
    :param es_instance_alias: Name of Elastic instance (for interface instantiation).
    :param **kw: Additional scroll keyword arguments. Valid options:
                 `size`: Integer, scroll size (number of documents per "scroll")
                 `scroll`: String, time value specifying how long the Elastic
                           cluster should keep the search context alive.
    """
    valid_kw = {"size", "scroll"}
    if not set(kw).issubset(valid_kw):
        raise ValueError(f"invalid keyword args: {set(kw) - valid_kw}")
    index_info = registry_entry(index_cname)
    es_interface = ElasticsearchInterface(get_es_instance(es_instance_alias))
    try:
        for results in es_interface.iter_scroll(index_info.alias, index_info.type,
                                                body=query, **kw):
            report_and_fail_on_shard_failures(results)
            for hit in results["hits"]["hits"]:
                yield hit
    except ElasticsearchException as e:
        raise ESError(e)


def count_query(index_cname, q):
    index_info = registry_entry(index_cname)
    es_interface = ElasticsearchInterface(get_es_new())
    return es_interface.count(index_info.alias, index_info.type, q)


class ScanResult(object):

    def __init__(self, count, iterator):
        self._iterator = iterator
        self.count = count

    def __iter__(self):
        for x in self._iterator:
            yield x


SIZE_LIMIT = 1000000


def report_and_fail_on_shard_failures(search_result):
    """
    Raise an ESShardFailure if there are shard failures in an ES search result (JSON)

    and report to datadog.
    The commcare.es.partial_results metric counts 1 per ES request with any shard failure.
    """
    if not isinstance(search_result, dict):
        return

    if search_result.get('_shards', {}).get('failed'):
        metrics_counter('commcare.es.partial_results')
        # Example message:
        #   "_shards: {'successful': 4, 'failed': 1, 'total': 5}"
        raise ESShardFailure('_shards: {!r}'.format(search_result.get('_shards')))
