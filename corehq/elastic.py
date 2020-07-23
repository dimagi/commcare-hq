import copy
import json
import logging
import time
from collections import namedtuple
from urllib.parse import unquote

from django.conf import settings

from memoized import memoized

from corehq.util.es.interface import ElasticsearchInterface
from corehq.util.metrics import metrics_counter
from dimagi.utils.chunked import chunked
from pillowtop.processors.elastic import send_to_elasticsearch as send_to_es

from corehq.apps.es.utils import flatten_field_dict
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
from corehq.util.files import TransientTempfile
from corehq.util.json import CommCareJSONEncoder


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


def doc_exists_in_es(index_info, doc_id_or_dict):
    """
    Check if a document exists, by ID or the whole document.
    """
    if isinstance(doc_id_or_dict, str):
        doc_id = doc_id_or_dict
    else:
        assert isinstance(doc_id_or_dict, dict)
        doc_id = doc_id_or_dict['_id']
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
    doc_exists = doc_exists_in_es(index_info, doc_id)
    return send_to_es(
        alias=index_info.alias,
        doc_type=index_info.type,
        doc_id=doc_id,
        es_getter=get_es_new,
        name="{}.{} <{}>:".format(send_to_elasticsearch.__module__,
                                  send_to_elasticsearch.__name__, index_name),
        data=doc,
        propagate_failure=True,
        update=doc_exists,
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

    return ScanResult(scroll_result.count, iter_export_docs())


def scroll_query(index_name, q, es_instance_alias=ES_DEFAULT_INSTANCE):
    es_meta = ES_META[index_name]
    try:
        return scan(
            get_es_instance(es_instance_alias),
            index_alias=es_meta.alias,
            doc_type=es_meta.type,
            query=q,
        )
    except ElasticsearchException as e:
        raise ESError(e)


class ScanResult(object):

    def __init__(self, count, iterator):
        self._iterator = iterator
        self.count = count

    def __iter__(self):
        for x in self._iterator:
            yield x


def scan(client, query=None, scroll='5m', **kwargs):
    """
    This is a copy of elasticsearch.helpers.scan, except this function returns
    a ScanResult (which includes the total number of documents), and removes
    some options from scan that we aren't using.

    Simple abstraction on top of the
    :meth:`~elasticsearch.Elasticsearch.scroll` api - a simple iterator that
    yields all hits as returned by underlining scroll requests.

    :arg client: instance of :class:`~elasticsearch.Elasticsearch` to use
    :arg query: body for the :meth:`~elasticsearch.Elasticsearch.search` api
    :arg scroll: Specify how long a consistent view of the index should be
        maintained for scrolled search

    Any additional keyword arguments will be passed to the initial
    :meth:`~elasticsearch.Elasticsearch.search` call::

        scan(es,
            query={"match": {"title": "python"}},
            index="orders-*",
            doc_type="books"
        )

    """
    if settings.ELASTICSEARCH_MAJOR_VERSION == 7:
        return scan_es7(client, query=query, scroll=scroll, **kwargs)
    else:
        return scan_es2(client, query=query, scroll=scroll, **kwargs)


def scan_es7(client, query=None, scroll='5m', **kwargs):

    # doc-type is not a valid kwarg for ES7
    kwargs.pop('doc_type', None)

    query = query.copy() if query else {}
    query["sort"] = "_doc"

    # initial search
    initial_resp = client.search(
        body=query, scroll=scroll, size=SCROLL_PAGE_SIZE_LIMIT, **kwargs
    )

    def fetch_all(initial_response):
        resp = initial_response
        scroll_id = resp.get('_scroll_id')

        while scroll_id and resp["hits"]["hits"]:
            for hit in resp["hits"]["hits"]:
                yield hit

            # check if we have any errors
            if resp["_shards"]["failed"]:
                logging.getLogger('elasticsearch.helpers').warning(
                    'Scroll request has failed on %d shards out of %d.',
                    resp['_shards']['failed'], resp['_shards']['total']
                )
            resp = client.scroll(
                body={"scroll_id": scroll_id, "scroll": scroll}
            )
            scroll_id = resp.get("_scroll_id")

    count = initial_resp.get("hits", {}).get("total", {}).get('value', None)
    return ScanResult(count, fetch_all(initial_resp))


def scan_es2(client, query=None, scroll='5m', **kwargs):
    kwargs['search_type'] = 'scan'
    # initial search
    es_interface = ElasticsearchInterface(client)
    initial_resp = es_interface.search(body=query, scroll=scroll, **kwargs)

    def fetch_all(initial_response):

        resp = initial_response
        scroll_id = resp.get('_scroll_id')
        if scroll_id is None:
            return
        iteration = 0

        while True:

            start = int(time.time() * 1000)
            resp = es_interface.scroll(scroll_id, scroll=scroll)
            for hit in resp['hits']['hits']:
                yield hit

            # check if we have any errrors
            if resp["_shards"]["failed"]:
                logging.getLogger('elasticsearch.helpers').warning(
                    'Scroll request has failed on %d shards out of %d.',
                    resp['_shards']['failed'], resp['_shards']['total']
                )

            scroll_id = resp.get('_scroll_id')
            # end of scroll
            if scroll_id is None or not resp['hits']['hits']:
                break

            iteration += 1

    count = initial_resp.get("hits", {}).get("total", None)
    return ScanResult(count, fetch_all(initial_resp))


SIZE_LIMIT = 1000000
SCROLL_PAGE_SIZE_LIMIT = 1000


def es_query(params=None, facets=None, terms=None, q=None, es_index=None, start_at=None, size=None, dict_only=False,
             fields=None, facet_size=None):
    if terms is None:
        terms = []
    if q is None:
        q = {}
    else:
        q = copy.deepcopy(q)
    if params is None:
        params = {}

    q["size"] = size if size is not None else q.get("size", SIZE_LIMIT)
    q["from"] = start_at or 0

    def get_or_init_anded_filter_from_query_dict(qdict):
        and_filter = qdict.get("filter", {}).pop("and", [])
        filter = qdict.pop("filter", None)
        if filter:
            and_filter.append(filter)
        return {"and": and_filter}

    filter = get_or_init_anded_filter_from_query_dict(q)

    def convert(param):
        #todo: find a better way to handle bools, something that won't break fields that may be 'T' or 'F' but not bool
        if param == 'T' or param is True:
            return 1
        elif param == 'F' or param is False:
            return 0
        return param

    for attr in params:
        if attr not in terms:
            attr_val = [convert(params[attr])] if not isinstance(params[attr], list) else [convert(p) for p in params[attr]]
            filter["and"].append({"terms": {attr: attr_val}})

    if facets:
        q["facets"] = q.get("facets", {})
        if isinstance(facets, list):
            for facet in facets:
                q["facets"][facet] = {"terms": {"field": facet, "size": facet_size or SIZE_LIMIT}}
        elif isinstance(facets, dict):
            q["facets"].update(facets)

    if filter["and"]:
        query = q.pop("query", {})
        q["query"] = {
            "filtered": {
                "filter": filter,
            }
        }
        q["query"]["filtered"]["query"] = query if query else {"match_all": {}}

    if fields is not None:
        q["fields"] = q.get("fields", [])
        q["fields"].extend(fields)

    if dict_only:
        return q

    es_index = es_index or 'domains'
    es_interface = ElasticsearchInterface(get_es_new())
    meta = ES_META[es_index]

    try:
        result = es_interface.search(meta.index, meta.type, body=q)
        report_and_fail_on_shard_failures(result)
    except ElasticsearchException as e:
        raise ESError(e)

    if fields is not None:
        for res in result['hits']['hits']:
            flatten_field_dict(res)

    return result


def stream_es_query(chunksize=100, **kwargs):
    size = kwargs.pop("size", None)
    kwargs.pop("start_at", None)
    kwargs["size"] = chunksize
    for i in range(0, size or SIZE_LIMIT, chunksize):
        kwargs["start_at"] = i
        res = es_query(**kwargs)
        if not res["hits"]["hits"]:
            return
        for hit in res["hits"]["hits"]:
            yield hit


def parse_args_for_es(request, prefix=None):
    """
    Parses a request's query string for url parameters. It specifically parses the facet url parameter so that each term
    is counted as a separate facet. e.g. 'facets=region author category' -> facets = ['region', 'author', 'category']
    """
    def strip_array(str):
        return str[:-2] if str.endswith('[]') else str

    params, facets = {}, []
    for attr in request.GET.lists():
        param, vals = attr[0], attr[1]
        if param == 'facets':
            facets = vals[0].split()
            continue
        if prefix:
            if param.startswith(prefix):
                params[strip_array(param[len(prefix):])] = [unquote(a) for a in vals]
        else:
            params[strip_array(param)] = [unquote(a) for a in vals]

    return params, facets


def generate_sortables_from_facets(results, params=None):
    """
    Sortable is a list of tuples containing the field name (e.g. Category) and a list of dictionaries for each facet
    under that field (e.g. HIV and MCH are under Category). Each facet's dict contains the query string, display name,
    count and active-status for each facet.
    """

    def generate_facet_dict(f_name, ft):
        # hack to get around unicode encoding issues. However it breaks this specific facet
        if isinstance(ft['term'], str):
            ft['term'] = ft['term'].encode('ascii', 'replace')

        return {'name': ft["term"],
                'count': ft["count"],
                'active': str(ft["term"]) in params.get(f_name, "")}

    sortable = []
    res_facets = results.get("facets", [])
    for facet in res_facets:
        if "terms" in res_facets[facet]:
            sortable.append((facet, [generate_facet_dict(facet, ft) for ft in res_facets[facet]["terms"] if ft["term"]]))

    return sortable


def fill_mapping_with_facets(facet_mapping, results, params=None):
    sortables = dict(generate_sortables_from_facets(results, params))
    for _, _, facets in facet_mapping:
        for facet_dict in facets:
            facet_dict["choices"] = sortables.get(facet_dict["facet"], [])
            if facet_dict.get('mapping'):
                for choice in facet_dict["choices"]:
                    choice["display"] = facet_dict.get('mapping').get(choice["name"], choice["name"])
    return facet_mapping


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
