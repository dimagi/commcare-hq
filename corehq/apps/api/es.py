import copy
import datetime
import json
import logging

from no_exceptions.exceptions import Http400

from dimagi.utils.parsing import ISO_DATE_FORMAT

from corehq.apps.api.models import ESCase, ESXFormInstance
from corehq.apps.api.util import object_does_not_exist
from corehq.apps.es import filters
from corehq.apps.es.cases import CaseES, case_adapter
from corehq.apps.es.exceptions import ESError
from corehq.apps.es.forms import FormES, form_adapter
from corehq.apps.es.utils import flatten_field_dict
from corehq.apps.reports.filters.forms import FormsByApplicationFilter
from corehq.util.es.elasticsearch import NotFoundError

logger = logging.getLogger('es')


class ESUserError(Http400):
    pass


class DateTimeError(ValueError):
    pass


class ESView:
    """Wrapper for an ES adapter that may be used in a web context

    Some errors are translated to HTTP errors.
    """

    doc_type = None
    model = None

    def __init__(self, domain):
        self.domain = domain.lower()

    def get_document(self, doc_id):
        try:
            doc = self.adapter.get(doc_id)
        except NotFoundError:
            raise object_does_not_exist(self.doc_type, doc_id)

        if doc.get('domain') != self.domain:
            raise object_does_not_exist(self.doc_type, doc_id)

        return self.model(doc) if self.model else doc

    def run_query(self, es_query):
        """
        Run a more advanced POST based ES query

        Returns the raw query json back, or None if there's an error
        """

        logger.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, json.dumps(es_query)))
        if 'fields' in es_query or 'script_fields' in es_query:
            #nasty hack to add domain field to query that does specific fields.
            #do nothing if there's no field query because we get everything
            fields = es_query.get('fields', [])
            fields.append('domain')
            es_query['fields'] = fields

        try:
            es_results = self.adapter.search(es_query)
        except ESError:
            if 'query_string' in es_query.get('query', {}).get('filtered', {}).get('query', {}):
                # the error may have been caused by a bad query string
                # re-run with no query string to check
                querystring = es_query['query']['filtered']['query']['query_string']['query']
                new_query = es_query
                new_query['query']['filtered']['query'] = {"match_all": {}}
                new_results = self.run_query(new_query)
                if new_results:
                    # the request succeeded without that query string
                    # an error with a blank query will return None
                    raise ESUserError("Error with elasticsearch query: %s" %
                        querystring)
            raise

        hits = []
        for res in es_results['hits']['hits']:
            if '_source' in res:
                res_domain = res['_source'].get('domain', None)
            elif 'fields' in res:
                res['fields'] = flatten_field_dict(res)
                res_domain = res['fields'].get('domain', None)

            # security check
            if res_domain == self.domain:
                hits.append(res)
            else:
                logger.info("Requester domain %s does not match result domain %s" % (
                    self.domain, res_domain))
        es_results['hits']['hits'] = hits
        return es_results

    def count_query(self, es_query):
        return self.adapter.count(es_query)


class CaseESView(ESView):
    """
    Expressive CaseES interface

    Yes, this is redundant with pieces of the v0_1.py CaseAPI - todo to merge these applications
    Which this should be the final say on ES access for Casedocs
    """
    adapter = case_adapter
    doc_type = "CommCareCase"
    model = ESCase


class FormESView(ESView):
    adapter = form_adapter
    doc_type = "XFormInstance"
    model = ESXFormInstance

    def run_query(self, es_query, **kwargs):
        es_results = super(FormESView, self).run_query(es_query)
        # hack, walk the results again, and if we have xmlns, populate human readable names
        # Note that `get_unknown_form_name` does not require the request, which is also
        # not necessarily available here. So `None` is passed here.
        form_filter = FormsByApplicationFilter(None, domain=self.domain)

        for res in es_results.get('hits', {}).get('hits', []):
            if '_source' in res:
                xmlns = res['_source'].get('xmlns', None)
                name = None
                if xmlns:
                    name = form_filter.get_unknown_form_name(xmlns,
                                                             app_id=res['_source'].get('app_id',
                                                                                       None),
                                                             none_if_not_found=True)
                if not name:
                    name = 'unknown'  # try to fix it below but this will be the default
                    # fall back
                    try:
                        if res['_source']['form'].get('@name', None):
                            name = res['_source']['form']['@name']
                        else:
                            backup = res['_source']['form'].get('#type', 'data')
                            if backup != 'data':
                                name = backup
                    except (TypeError, KeyError):
                        pass

                res['_source']['es_readable_name'] = name

        return es_results


class ElasticAPIQuerySet(object):
    """
    An abstract representation of an elastic search query,
    modeled somewhat after Django's QuerySet but with
    the only important goal being compatibility
    with Tastypie's classes. Key capabilities, by piece of
    Tastypie:

    Pagination:

    - `__getitem__([start:stop])` which should efficiently pass the bounds on to ES
    - `count()` which should efficiently ask ES for the total matching (regardless of slice)

    Sorting:

    - order_by('field') or order_by('-field') both become ES service-side sort directives

    Serialization:

    - `__iter__()`

    """

    # Also note https://github.com/llonchj/django-tastypie-elasticsearch/ which is
    # not very mature, plus this code below may involve Dimagic-specific assumptions

    def __init__(self, es_client, payload=None, model=None):
        """
        Instantiate with an entire ElasticSearch payload,
        since "query", "filter", etc, all exist alongside
        each other.
        """
        self.es_client = es_client
        self.payload = payload
        self.model = model
        self.__results = None

    def with_fields(self, es_client=None, payload=None, model=None):
        "Clones this queryset, optionally changing some fields"
        return ElasticAPIQuerySet(es_client=es_client or self.es_client,
                          payload=payload or self.payload,
                          model=model or self.model)

    @property
    def results(self):
        if self.__results is None:
            self.__results = self.es_client.run_query(self.payload)
        return self.__results

    def count(self):
        return self.es_client.count_query(self.payload)

    def order_by(self, *fields):

        new_payload = copy.deepcopy(self.payload)

        new_payload['sort'] = []

        for field in fields:
            if not field:
                continue

            direction = 'asc'
            missing_dir = '_first'
            if field[0] == '-':
                direction = 'desc'
                missing_dir = '_last'
                field = field[1:]

            new_payload['sort'].append({field: {
                'order': direction,
                "missing": missing_dir
            }})

        return self.with_fields(payload=new_payload)

    def __len__(self):
        # Note that this differs from `count` in that it actually performs the query and measures
        # only those objects returned
        return len(self.results['hits']['hits'])

    def __iter__(self):
        wrap = self.model or (lambda v: v)
        for jvalue in self.results['hits']['hits']:
            yield wrap(jvalue['_source'])

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            if idx.start < 0 or idx.stop < 0:
                # This actually could be supported with varying degrees of efficiency
                raise NotImplementedError('Negative index in slice not supported.')

            new_payload = copy.deepcopy(self.payload)
            new_payload['from'] = new_payload.get('from', 0) + (idx.start or 0)

            if idx.stop is not None:
                new_payload['size'] = max(0, idx.stop - (idx.start or 0))

            return self.with_fields(payload=new_payload)

        elif isinstance(idx, int):
            if idx >= 0:
                # Leverage efficicent backend slicing
                return list(self[idx:idx + 1])[0]
            else:
                # This actually could be supported with varying degrees of efficiency
                raise NotImplementedError('Negative index not supported.')
        else:
            raise TypeError('Unsupported type: %s', type(idx))


SUPPORTED_DATE_FORMATS = [
    ISO_DATE_FORMAT,
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%dT%H:%M:%S.%f',
    '%Y-%m-%dT%H:%MZ',  # legacy Case API date format
]


def validate_date(date):
    for pattern in SUPPORTED_DATE_FORMATS:
        try:
            return datetime.datetime.strptime(date, pattern)
        except ValueError:
            pass

    # No match
    raise DateTimeError("Unknown date format: {}".format(date))


TASTYPIE_RESERVED_GET_PARAMS = ['api_key', 'username', 'format']
RESERVED_QUERY_PARAMS = set(['limit', 'offset', 'order_by', 'q'] + TASTYPIE_RESERVED_GET_PARAMS)


class DateRangeParams(object):
    def __init__(self, param, term=None):
        self.term = term or param
        self.start_param = '{}_start'.format(param)
        self.end_param = '{}_end'.format(param)

    def consume_params(self, raw_params):
        start = raw_params.pop(self.start_param, None)
        end = raw_params.pop(self.end_param, None)
        if start:
            start = validate_date(start)
        if end:
            end = validate_date(end)

        if start or end:
            # Note that dates are already in a string format when they arrive as query params
            return filters.date_range(self.term, gte=start, lte=end)


class TermParam(object):
    """Allows for use of params that differ between the API and the ES mapping

    It's also used without the `term` argument for non-analyzed values, to
    prevent them from being coerced to lowercase
    """
    def __init__(self, param, term=None, analyzed=False):
        self.param = param
        self.term = term or param
        self.analyzed = analyzed

    def consume_params(self, raw_params):
        value = raw_params.pop(self.param, None)
        if value:
            # convert non-analyzed values to lower case
            value = value.lower() if self.analyzed else value
            return filters.term(self.term, value)


class XFormServerModifiedParams:
    param = 'server_modified_on'

    def consume_params(self, raw_params):
        value = raw_params.pop(self.param, None)
        if value:
            return filters.OR(
                filters.AND(
                    filters.NOT(filters.missing(self.param)), filters.range_filter(self.param, **value)
                ),
                filters.AND(
                    filters.missing(self.param), filters.range_filter("received_on", **value)
                )
            )


xform_param_consumers = [
    TermParam('xmlns', 'xmlns.exact'),
    TermParam('xmlns.exact'),
    TermParam('case_id', '__retrieved_case_ids'),
    DateRangeParams('received_on'),
    DateRangeParams('server_modified_on'),
    DateRangeParams('server_date_modified', 'server_modified_on'),
    DateRangeParams('indexed_on', 'inserted_at'),
]

case_param_consumers = [
    TermParam('case_name', 'name', analyzed=True),
    TermParam('case_type', 'type', analyzed=True),
    TermParam('type.exact'),
    TermParam('name.exact'),
    TermParam('external_id.exact'),
    TermParam('contact_phone_number'),
    DateRangeParams('server_modified_on'),
    DateRangeParams('date_modified', 'modified_on'),
    DateRangeParams('server_date_modified', 'server_modified_on'),
    DateRangeParams('indexed_on', 'inserted_at'),
]


def _validate_and_get_es_filter(search_param):
    _filter = search_param.pop('filter', None)
    if not _filter:
        # not a supported query
        raise Http400
    try:
        # custom use case by 'enveritas' project for Form API
        date_range = _filter['range']['inserted_at']
        return {
            'range': {'inserted_at': date_range}
        }
    except KeyError:
        pass
    try:
        # custom filter from Data export tool
        _range = None
        try:
            _range = _filter['or'][0]['and'][0]['range']['server_modified_on']
        except KeyError:
            try:
                _range = _filter['or'][0]['and'][1]['range']['server_modified_on']
            except KeyError:
                pass

        if _range:
            return XFormServerModifiedParams().consume_params({'server_modified_on': _range})
        else:
            raise Http400
    except (KeyError, AssertionError):
        raise Http400


def es_query_from_get_params(search_params, domain, doc_type='form'):
    query_params = {
        param: value
        for param, value in search_params.items()
        if param not in RESERVED_QUERY_PARAMS and not param.endswith('__full')
    }

    if doc_type == 'form':
        query = FormES().remove_default_filters().domain(domain)
        if query_params.pop('include_archived', None) is not None:
            query = query.filter(filters.OR(
                filters.term('doc_type', 'xforminstance'),
                filters.term('doc_type', 'xformarchived'),
            ))
        else:
            query = query.filter(filters.term('doc_type', 'xforminstance'))
        query_param_consumers = xform_param_consumers
    elif doc_type == 'case':
        query = CaseES().domain(domain)
        query_param_consumers = case_param_consumers
    else:
        raise AssertionError("unknown doc type")

    if '_search' in query_params:
        # This is undocumented usecase by Data export tool and one custom project
        #   Validate that the passed in param is one of these two expected
        _filter = _validate_and_get_es_filter(json.loads(query_params.pop('_search')))
        query = query.filter(_filter)

    for consumer in query_param_consumers:
        try:
            payload_filter = consumer.consume_params(query_params)
        except DateTimeError as e:
            raise Http400("Bad query parameter: {}".format(str(e)))

        if payload_filter:
            query = query.filter(payload_filter)

    # add unconsumed filters
    for param, value in query_params.items():
        # assume these fields are analyzed in ES so convert to lowercase
        # Any fields that are not analyzed in ES should be in the ``query_param_consumers`` above
        value = value.lower()
        query = query.filter(filters.term(param, value))

    return query.raw_query


def flatten_list(list_2d):
    flat_list = []
    # Iterate through the outer list
    for element in list_2d:
        if isinstance(element, list):
            # If the element is of type list, iterate through the sublist
            for item in element:
                flat_list.append(item)
        else:
            flat_list.append(element)
    return flat_list
