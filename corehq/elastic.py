from urllib import unquote
import rawes
from django.conf import settings
from corehq.pillows.mappings.case_mapping import CASE_INDEX
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX
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
    "domains": DOMAIN_INDEX + '/hqdomain/_search'
}

ADD_TO_ES_FILTER = {
    "forms": [
        {"not": {"in": {"doc_type": ["xformduplicate", "xformdeleted"]}}},
        {"not": {"missing": {"field": "xmlns"}}},
        {"not": {"missing": {"field": "form.meta.userID"}}},
    ],
    "users": [{"term": {"doc_type": "CommCareUser"}}],
}

DATE_FIELDS = {
    "forms": "received_on",
    "cases": "opened_on",
    "users": "created_on",
}


def get_stats_data(domains, histo_type, datespan, interval="day"):
    histo_data = dict([(d['display_name'],
                        es_histogram(histo_type, d["names"], datespan.startdate_display, datespan.enddate_display))
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
        q["filter"]["and"].extend(ADD_TO_ES_FILTER.get(histo_type, []))

        return es_query(q=q, es_url=ES_URLS[histo_type], size=1)["hits"]["total"]

    return {
        'histo_data': histo_data,
        'initial_values': dict([(dom["display_name"],
                                 _total_until_date(histo_type, dom["names"])) for dom in domains]),
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


def es_histogram(histo_type, domains=None, startdate=None, enddate=None, tz_diff=None, interval="day"):
    q = {"query": {"match_all":{}}}

    if domains is not None:
        q["query"] = {"in" : {"domain.exact": domains}}

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


def es_query(params=None, facets=None, terms=None, q=None, es_url=None, start_at=None, size=None, dict_only=False):
    """
        Any filters you include in your query should an and filter
        todo: intelligently deal with preexisting filters
    """
    if terms is None:
        terms = []
    if q is None:
        q = {}
    if params is None:
        params = {}

    q["size"] = size if size is not None else q.get("size", 9999)
    q["from"] = start_at or 0
    q["filter"] = q.get("filter", {})
    q["filter"]["and"] = q["filter"].get("and", [])

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
            q["filter"]["and"].append({"terms": {attr: attr_val}})

    def facet_filter(facet):
        return [clause for clause in q["filter"]["and"] if facet not in clause.get("terms", [])]

    if facets:
        q["facets"] = q.get("facets", {})
        for facet in facets:
            q["facets"][facet] = {"terms": {"field": facet, "size": 9999}}

    if q.get('facets'):
        for facet in q["facets"]:
            if "facet_filter" not in q["facets"][facet]:
                q["facets"][facet]["facet_filter"] = {"and": []}
            q["facets"][facet]["facet_filter"]["and"].extend(facet_filter(facet))

    if not q['filter']['and']:
        del q["filter"]

    if dict_only:
        return q

    es_url = es_url or DOMAIN_INDEX + '/hqdomain/_search'

    es = get_es()
    ret_data = es.get(es_url, data=q)

    return ret_data


def stream_es_query(chunksize=100, **kwargs):
    size = kwargs.pop("size", None)
    kwargs.pop("start_at", None)
    kwargs["size"] = chunksize
    for i in range(0, size or 9999999, chunksize):
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
