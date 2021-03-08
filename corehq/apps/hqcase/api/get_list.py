import datetime
from itertools import chain

from dateutil.parser import parse

from dimagi.utils.parsing import FALSE_STRINGS

from corehq.apps.es import case_search
from corehq.apps.es import cases as case_es

from .core import UserError, serialize_es_case

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 5000


def _to_boolean(val):
    return not (val == '' or val.lower() in FALSE_STRINGS)


def _to_int(val, param_name):
    try:
        return int(val)
    except ValueError:
        raise UserError(f"'{val}' is not a valid value for '{param_name}'")


class Filter:
    def __init__(self, field, filter_fn):
        self.field = field
        self.filter_fn = filter_fn

    def consume_params(self, params):
        if self.field in params:
            yield self.filter_fn(params.pop(self.field))


def _consume_compound_params(field, params):
    """eg: {last_modified.gte: 2020-03-01} => gte, 2020-03-01"""
    keys = [key for key in params if key.split('.')[0] == field]
    for key in keys:
        if not key.count('.') == 1:
            raise UserError(f"'{key}' is not a valid parameter.")
        field, qualifier = key.split('.')
        val = params.pop(key)
        yield qualifier, val


class DateFilter:
    def __init__(self, field, filter_fn):
        self.field = field
        self.filter_fn = filter_fn

    def consume_params(self, params):
        for range_, val in _consume_compound_params(self.field, params):
            if range_ not in ['gt', 'gte', 'lte', 'lt']:
                raise UserError(f"'{range_}' is not a valid date range.")
            date = self._get_date(val)
            yield self.filter_fn(**{range_: date})

    def _get_date(self, val):
        try:
            # If it's only a date, don't turn it into a datetime
            return datetime.datetime.strptime(val, '%Y-%m-%d').date()
        except ValueError:
            try:
                return parse(val)
            except ValueError:
                raise UserError(f"Cannot parse datetime '{val}'")


class CustomPropertyFilter:
    def __init__(self, field):
        self.field = field

    def consume_params(self, params):
        for case_property, val in _consume_compound_params(self.field, params):
            if val == "":
                yield case_search.case_property_missing(case_property)
            else:
                yield case_search.exact_case_property_text_query(case_property, val)


FILTERS = [
    Filter('external_id', case_search.external_id),
    Filter('case_type', case_es.case_type),
    Filter('owner_id', case_es.owner),
    Filter('case_name', case_es.case_name),
    Filter('closed', lambda val: case_es.is_closed(_to_boolean(val))),
    DateFilter('last_modified', case_es.modified_range),
    DateFilter('server_last_modified', case_es.server_modified_range),
    DateFilter('date_opened', case_es.opened_range),
    DateFilter('date_closed', case_es.closed_range),
    CustomPropertyFilter('property'),
]


def get_list(domain, params):
    start = _to_int(params.pop('offset', 0), 'offset')
    page_size = _to_int(params.pop('limit', DEFAULT_PAGE_SIZE), 'limit')
    if page_size > MAX_PAGE_SIZE:
        raise UserError(f"You cannot request more than {MAX_PAGE_SIZE} cases per request.")

    query = (case_search.CaseSearchES()
             .domain(domain)
             .size(page_size)
             .start(start)
             .sort("@indexed_on"))

    for filter_ in FILTERS:
        for es_filter in filter_.consume_params(params):
            query = query.filter(es_filter)

    if params:
        unrecognized = ', '.join(params.keys())
        raise UserError(f"The following parameters were not recognized: {unrecognized}")

    return [serialize_es_case(case) for case in query.run().hits]
