import copy
from urllib import unquote
import rawes
from django.conf import settings
from corehq.pillows.mappings.app_mapping import APP_INDEX
from corehq.pillows.mappings.case_mapping import CASE_INDEX
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX
from corehq.pillows.mappings.group_mapping import GROUP_INDEX
from corehq.pillows.mappings.sms_mapping import SMS_INDEX
from corehq.pillows.mappings.tc_sms_mapping import TCSMS_INDEX
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX


def get_es(timeout=30):
    """
    Get a handle to the configured elastic search DB
    """
    return rawes.Elastic('%s:%s' % (settings.ELASTICSEARCH_HOST, 
                                    settings.ELASTICSEARCH_PORT),
                         timeout=timeout)


ES_URLS = {
    "forms": XFORM_INDEX + '/xform/_search',
    "cases": CASE_INDEX + '/case/_search',
    "users": USER_INDEX + '/user/_search',
    "domains": DOMAIN_INDEX + '/hqdomain/_search',
    "apps": APP_INDEX + '/app/_search',
    "groups": GROUP_INDEX + '/group/_search',
    "sms": SMS_INDEX + '/sms/_search',
    "tc_sms": TCSMS_INDEX + '/tc_sms/_search',
}

ADD_TO_ES_FILTER = {
    "forms": [
        {"term": {"doc_type": "xforminstance"}},
        {"not": {"missing": {"field": "xmlns"}}},
        {"not": {"missing": {"field": "form.meta.userID"}}},
    ],
    "users": [
        {"term": {"doc_type": "CommCareUser"}},
        {"term": {"base_doc": "couchuser"}},
        {"term": {"is_active": True}},
    ],
}

DATE_FIELDS = {
    "forms": "received_on",
    "cases": "opened_on",
    "users": "created_on",
    "sms": 'date',
    "tc_sms": 'date',
}

ES_MAX_CLAUSE_COUNT = 1024  #  this is what ES's maxClauseCount is currently set to,
                            #  can change this config value if we want to support querying over more domains


class ESError(Exception):
    pass


def run_query(url, q):
    return get_es().get(url, data=q)


def get_stats_data(domains, histo_type, datespan, interval="day"):
    histo_data = dict([(d['display_name'],
                        es_histogram(histo_type, d["names"], datespan.startdate_display, datespan.enddate_display, interval=interval))
                        for d in domains])

    def _total_until_date(histo_type, doms=None):
        query = {"in": {"domain.exact": doms}} if doms is not None else {"match_all": {}}
        q = {
            "query": query,
            "filter": {
                "and": [
                    {"range": {DATE_FIELDS[histo_type]: {"lt": datespan.startdate_display}}},
                ],
            },
        }
        q["filter"]["and"].extend(ADD_TO_ES_FILTER.get(histo_type, [])[:])

        return es_query(q=q, es_url=ES_URLS[histo_type], size=0)["hits"]["total"]

    return {
        'histo_data': histo_data,
        'initial_values': dict([(dom["display_name"],
                                 _total_until_date(histo_type, dom["names"])) for dom in domains]),
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


def es_histogram(histo_type, domains=None, startdate=None, enddate=None, tz_diff=None, interval="day", q=None):
    q = q or {"query": {"match_all":{}}}

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

    if tz_diff:
        q["facets"]["histo"]["date_histogram"]["time_zone"] = tz_diff

    q["facets"]["histo"]["facet_filter"]["and"].extend(ADD_TO_ES_FILTER.get(histo_type, []))

    es = get_es()
    ret_data = es.get(ES_URLS[histo_type], data=q)
    return ret_data["facets"]["histo"]["entries"]


SIZE_LIMIT = 1000000
def es_query(params=None, facets=None, terms=None, q=None, es_url=None, start_at=None, size=None, dict_only=False,
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

    es_url = es_url or DOMAIN_INDEX + '/hqdomain/_search'

    es = get_es()
    result = es.get(es_url, data=q)

    if 'error' in result:
        msg = result['error']
        raise ESError(msg)

    return result


def es_wrapper(index, domain=None, q=None, doc_type=None, fields=None,
        start_at=None, size=None, sort_by=None, order=None, return_count=False,
        filters=None):
    """
    This is a flat wrapper for es_query.

    To sort, specify the path to the relevant field
    and the order ("asc" or "desc")
    eg: sort_by=form.meta.timeStart, order="asc"
    """
    if index not in ES_URLS:
        msg = "%s is not a valid ES index.  Available options are: %s" % (
            index, ', '.join(ES_URLS.keys()))
        raise IndexError(msg)

    # query components
    match_all = {"match_all": {}}
    if isinstance(q, dict):
        query_string = q
    else:
        query_string = {"query_string": {"query": q}}
    doc_type_filter = {"term": {"doc_type": doc_type}}
    domain_filter = {"or": [
        {"term": {"domain.exact": domain}},
        {"term": {"domain_memberships.domain.exact": domain}},
    ]}

    # actual query
    query = {"query": {
        "filtered": {
            "filter": {"and": []},
            "query": query_string if q else match_all
        }
    }}

    # add filters
    es_filters = query["query"]["filtered"]["filter"]["and"]
    if domain:
        es_filters.append(domain_filter)
    if doc_type:
        es_filters.append(doc_type_filter)
    if not doc_type and not domain:
        es_filters.append(match_all)
    if filters:
        es_filters.extend(filters)
    es_filters.extend(ADD_TO_ES_FILTER.get(index, [])[:])
    if sort_by:
        assert(order in ["asc", "desc"]),\
            'To sort, you must specify the order as "asc" or "desc"'
        query["sort"] = [{sort_by: {"order": order}}]

    # make query
    res = es_query(
        es_url=ES_URLS[index],
        q=query,
        fields=fields,
        start_at=start_at,
        size=size,
    )

    # parse results
    if fields is not None:
        hits = [r['fields'] for r in res['hits']['hits']]
    else:
        hits = [r['_source'] for r in res['hits']['hits']]

    if return_count:
        total = res['hits']['total']
        return total, hits
    return hits


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


def stream_esquery(esquery, chunksize=100):
    size = esquery._size if esquery._size is not None else SIZE_LIMIT
    start = esquery._start if esquery._start is not None else 0
    for chunk_start in range(start, start + size, chunksize):
        for hit in esquery.size(chunksize).start(chunk_start).run().raw_hits:
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

DAY_VALUE = 86400000
def format_histo_data(data, name, min_t=None, max_t=None):
    data = dict([(d["time"], d["count"]) for d in data])
    times = data.keys()
    min_t, max_t = min_t or min(times), max_t or max(times)
    time = min_t
    values = []
    while time <= max_t:
        values.append([time, data.get(time, 0)])
        time += DAY_VALUE
    return {"key": name, "values": values}
