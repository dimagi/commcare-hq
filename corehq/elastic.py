import json
import logging
import time

from django.conf import settings

from memoized import memoized

from dimagi.utils.chunked import chunked
from pillowtop.processors.elastic import send_to_elasticsearch as send_to_es

from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX_INFO
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX_INFO
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
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


def send_to_elasticsearch(index_name, doc, delete=False, es_merge_update=False):
    """
    Utility method to update the doc in elasticsearch.
    Duplicates the functionality of pillowtop but can be called directly.
    """
    doc_id = doc['_id']
    if isinstance(doc_id, bytes):
        doc_id = doc_id.decode('utf-8')
    index_info = ES_META[index_name]
    return send_to_es(
        index_info=index_info,
        doc_type=index_info.type,
        doc_id=doc_id,
        es_getter=get_es_new,
        name="{}.{} <{}>:".format(send_to_elasticsearch.__module__,
                                  send_to_elasticsearch.__name__, index_name),
        data=doc,
        delete=delete,
        es_merge_update=es_merge_update,
    )


def refresh_elasticsearch_index(index_name):
    es_meta = ES_META[index_name]
    es = get_es_new()
    es.indices.refresh(index=es_meta.alias)


# Todo; These names can be migrated to use hq_index_name attribute constants in future
ES_META = {
    "forms": XFORM_INDEX_INFO,
    "cases": CASE_INDEX_INFO,
    "users": USER_INDEX_INFO,
    "domains": DOMAIN_INDEX_INFO,
    "apps": APP_INDEX_INFO,
    "groups": GROUP_INDEX_INFO,
    "sms": SMS_INDEX_INFO,
    "report_cases": REPORT_CASE_INDEX_INFO,
    "report_xforms": REPORT_XFORM_INDEX_INFO,
    "case_search": CASE_SEARCH_INDEX_INFO,
}

ES_MAX_CLAUSE_COUNT = 1024  #  this is what ES's maxClauseCount is currently set to,
                            #  can change this config value if we want to support querying over more domains


class ESError(Exception):
    pass


class ESShardFailure(ESError):
    pass


def run_query(index_name, q, debug_host=None, es_instance_alias=ES_DEFAULT_INSTANCE):
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

    es_meta = ES_META[index_name]
    try:
        results = es_interface.search(es_meta.alias, es_meta.type, body=q)
        report_and_fail_on_shard_failures(results)
        return results
    except ElasticsearchException as e:
        raise ESError(e)


def mget_query(index_name, ids):
    if not ids:
        return []

    es_interface = ElasticsearchInterface(get_es_new())
    es_meta = ES_META[index_name]
    try:
        return es_interface.get_bulk_docs(es_meta.alias, es_meta.type, ids)
    except ElasticsearchException as e:
        raise ESError(e)


def iter_es_docs(index_name, ids):
    """Returns a generator which pulls documents from elasticsearch in chunks"""
    for ids_chunk in chunked(ids, 100):
        yield from mget_query(index_name, ids_chunk)


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


def scroll_query(index_name, q, es_instance_alias=ES_DEFAULT_INSTANCE):
    es_meta = ES_META[index_name]
    es_interface = ElasticsearchInterface(get_es_instance(es_instance_alias))
    return es_interface.scan(es_meta.alias, q, es_meta.type)


def count_query(index_name, q):
    es_meta = ES_META[index_name]
    es_interface = ElasticsearchInterface(get_es_new())
    return es_interface.count(es_meta.alias, es_meta.type, q)

class ScanResult(object):

    def __init__(self, count, iterator):
        self._iterator = iterator
        self.count = count

    def __iter__(self):
        for x in self._iterator:
            yield x


SIZE_LIMIT = 1000000
SCROLL_PAGE_SIZE_LIMIT = 1000


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
