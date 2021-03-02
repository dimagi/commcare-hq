import datetime
from itertools import chain

from dateutil.parser import parse

from dimagi.utils.parsing import FALSE_STRINGS

from corehq.apps.es import case_search
from corehq.apps.es import cases as case_es

from .core import UserError, serialize_es_case

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 5000
CUSTOM_PROPERTY_PREFIX = 'property.'


def _to_boolean(val):
    return val.lower() not in [''] + list(FALSE_STRINGS)


def _to_int(val, param_name):
    try:
        return int(val)
    except ValueError:
        raise UserError(f"'{val}' is not a valid value for '{param_name}'")


def _make_date_filter(date_filter, param):

    def filter_fn(val):
        try:
            # If it's only a date, don't turn it into a datetime
            val = datetime.date.fromisoformat(val)
        except ValueError:
            try:
                val = parse(val)
            except ValueError:
                raise UserError(f"Cannot parse datetime '{val}'")
        return date_filter(**{param: val})

    return filter_fn


def _to_date_filters(field, date_filter):
    return [
        (f'{field}.gt', _make_date_filter(date_filter, 'gt')),
        (f'{field}.gte', _make_date_filter(date_filter, 'gte')),
        (f'{field}.lte', _make_date_filter(date_filter, 'lte')),
        (f'{field}.lt', _make_date_filter(date_filter, 'lt')),
    ]


FILTERS = {
    'external_id': case_search.external_id,
    'case_type': case_es.case_type,
    'owner_id': case_es.owner,
    'case_name': case_es.case_name,
    'closed': lambda val: case_es.is_closed(_to_boolean(val)),
}
FILTERS.update(chain(*[
    _to_date_filters('last_modified', case_es.modified_range),
    _to_date_filters('server_last_modified', case_es.server_modified_range),
    _to_date_filters('date_opened', case_es.opened_range),
    _to_date_filters('date_closed', case_es.closed_range),
]))


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

    for k, v in params.items():
        if k.startswith(CUSTOM_PROPERTY_PREFIX):
            query = query.filter(_get_custom_property_filter(k, v))
        elif k in FILTERS:
            query = query.filter(FILTERS[k](v))
        else:
            raise UserError(f"'{k}' is not a valid parameter.")

    return [serialize_es_case(case) for case in query.run().hits]


def _get_custom_property_filter(k, v):
    prop = k[len(CUSTOM_PROPERTY_PREFIX):]
    if v == "":
        return case_search.case_property_missing(prop)
    return case_search.exact_case_property_text_query(prop, v)
