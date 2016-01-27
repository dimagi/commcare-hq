import copy
from collections import namedtuple
from urllib import unquote
from elasticsearch import Elasticsearch
from django.conf import settings
from elasticsearch.exceptions import ElasticsearchException, RequestError

from corehq.apps.es.utils import flatten_field_dict
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX
from pillowtop.listener import send_to_elasticsearch as send_to_es
from corehq.pillows.mappings.app_mapping import APP_INDEX
from corehq.pillows.mappings.case_mapping import CASE_INDEX
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX
from corehq.pillows.mappings.group_mapping import GROUP_INDEX
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX
from corehq.pillows.mappings.sms_mapping import SMS_INDEX
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX


def get_es_new():
    """
    Get a handle to the configured elastic search DB.
    Returns an elasticsearch.Elasticsearch instance.
    """
    return Elasticsearch([{
        'host': settings.ELASTICSEARCH_HOST,
        'port': settings.ELASTICSEARCH_PORT,
    }])


def doc_exists_in_es(index, doc_id):
    es_meta = ES_META[index]
    return get_es_new().exists(es_meta.index, doc_id, doc_type=es_meta.type)


def send_to_elasticsearch(index, doc, delete=False):
    """
    Utility method to update the doc in elasticsearch.
    Duplicates the functionality of pillowtop but can be called directly.
    """
    doc_id = doc['_id']
    es_meta = ES_META[index]
    doc_exists = doc_exists_in_es(index, doc_id)
    return send_to_es(
        index=es_meta.index,
        doc_type=es_meta.type,
        doc_id=doc_id,
        es_getter=get_es_new,
        name="{}.{} <{}>:".format(send_to_elasticsearch.__module__,
                                  send_to_elasticsearch.__name__, index),
        data=doc,
        except_on_failure=True,
        update=doc_exists,
        delete=delete,
    )

EsMeta = namedtuple('EsMeta', 'index, type')

ES_META = {
    "forms": EsMeta(XFORM_INDEX, 'xform'),
    "cases": EsMeta(CASE_INDEX, 'case'),
    "active_cases": EsMeta(CASE_INDEX, 'case'),
    "users": EsMeta(USER_INDEX, 'user'),
    "users_all": EsMeta(USER_INDEX, 'user'),
    "domains": EsMeta(DOMAIN_INDEX, 'hqdomain'),
    "apps": EsMeta(APP_INDEX, 'app'),
    "groups": EsMeta(GROUP_INDEX, 'group'),
    "sms": EsMeta(SMS_INDEX, 'sms'),
    "report_cases": EsMeta(REPORT_CASE_INDEX, 'report_case'),
    "report_xforms": EsMeta(REPORT_XFORM_INDEX, 'report_xform'),
}

ADD_TO_ES_FILTER = {
    "forms": [
        {"term": {"doc_type": "xforminstance"}},
        {"not": {"missing": {"field": "xmlns"}}},
        {"not": {"missing": {"field": "form.meta.userID"}}},
    ],
    "archived_forms": [
        {"term": {"doc_type": "xformarchived"}},
        {"not": {"missing": {"field": "xmlns"}}},
        {"not": {"missing": {"field": "form.meta.userID"}}},
    ],
    "users": [
        {"term": {"doc_type": "CommCareUser"}},
        {"term": {"base_doc": "couchuser"}},
        {"term": {"is_active": True}},
    ],
    "web_users": [
        {"term": {"doc_type": "WebUser"}},
        {"term": {"base_doc": "couchuser"}},
        {"term": {"is_active": True}},
    ],
    "users_all": [
        {"term": {"base_doc": "couchuser"}},
    ],
    "active_cases": [
        {"term": {"closed": False}},
    ],
}

DATE_FIELDS = {
    "forms": "received_on",
    "cases": "opened_on",
    "active_cases": "modified_on",
    "users": "created_on",
    "users_all": "created_on",
    "sms": 'date',
}

ES_MAX_CLAUSE_COUNT = 1024  #  this is what ES's maxClauseCount is currently set to,
                            #  can change this config value if we want to support querying over more domains


class ESError(Exception):
    pass


def run_query(index_name, q):
    es_meta = ES_META[index_name]
    try:
        return get_es_new().search(es_meta.index, es_meta.type, body=q)
    except RequestError as e:
        raise ESError(e)


def es_histogram(histo_type, domains=None, startdate=None, enddate=None,
        interval="day", filters=[]):
    q = {"query": {"match_all":{}}}

    if domains is not None:
        q["query"] = {"bool": {"must": [q["query"], {"in": {"domain.exact": domains}}]}}

    date_field = DATE_FIELDS[histo_type]

    q.update({
        "facets": {
            "histo": {
                "date_histogram": {
                    "field": date_field,
                    "interval": interval
                },
                "facet_filter": {
                    "and": [{
                        "range": {
                            date_field: {
                                "from": startdate,
                                "to": enddate
                            }}}]}}},
        "size": 0
    })

    q["facets"]["histo"]["facet_filter"]["and"].extend(filters)
    q["facets"]["histo"]["facet_filter"]["and"].extend(ADD_TO_ES_FILTER.get(histo_type, []))

    es_meta = ES_META[histo_type]
    ret_data = get_es_new().search(es_meta.index, es_meta.type, body=q)
    return ret_data["facets"]["histo"]["entries"]


SIZE_LIMIT = 1000000
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
    es = get_es_new()
    meta = ES_META[es_index]

    try:
        result = es.search(meta.index, meta.type, body=q)
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
    for attr in request.GET.iterlists():
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
        if isinstance(ft['term'], unicode): #hack to get around unicode encoding issues. However it breaks this specific facet
            ft['term'] = ft['term'].encode('ascii','replace')

        return {'name': ft["term"],
                'count': ft["count"],
                'active': str(ft["term"]) in params.get(f_name, "")}

    sortable = []
    res_facets = results.get("facets", [])
    for facet in res_facets:
        if res_facets[facet].has_key("terms"):
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
