import datetime
from base64 import b64decode, b64encode
from itertools import chain
from django.utils.http import urlencode

from django.http import QueryDict

from dateutil.parser import parse

from dimagi.utils.parsing import FALSE_STRINGS

from corehq.apps.case_search.filter_dsl import (
    CaseFilterError,
    build_filter_from_xpath,
)
from corehq.apps.es import case_search
from corehq.apps.es import cases as case_es

from .core import UserError, serialize_es_case

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 5000
CUSTOM_PROPERTY_PREFIX = 'property.'


def _to_boolean(val):
    return not (val == '' or val.lower() in FALSE_STRINGS)


def _to_int(val, param_name):
    try:
        return int(val)
    except ValueError:
        raise UserError(f"'{val}' is not a valid value for '{param_name}'")


def _make_date_filter(date_filter, param):

    def filter_fn(val):
        try:
            # If it's only a date, don't turn it into a datetime
            val = datetime.datetime.strptime(val, '%Y-%m-%d').date()
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
    'index': case_search.reverse_index_case_query,
}
FILTERS.update(chain(*[
    _to_date_filters('last_modified', case_es.modified_range),
    _to_date_filters('server_last_modified', case_es.server_modified_range),
    _to_date_filters('date_opened', case_es.opened_range),
    _to_date_filters('date_closed', case_es.closed_range),
    _to_date_filters('indexed_on', case_search.indexed_on),
]))


def get_list(domain, params):
    if 'cursor' in params:
        params_string = b64decode(params['cursor']).decode('utf-8')
        params = QueryDict(params_string).dict()

    es_result = _run_query(domain, params)
    hits = es_result.hits
    ret = {
        "matching_records": es_result.total,
        "cases": [serialize_es_case(case) for case in hits],
    }

    cases_in_result = len(hits)
    if cases_in_result and es_result.total > cases_in_result:
        cursor = urlencode({**params, **{'indexed_on.gte': hits[-1]["@indexed_on"]}})
        ret['next'] = {'cursor': b64encode(cursor.encode('utf-8'))}

    return ret


def _run_query(domain, params):
    params = params.copy()
    page_size = _to_int(params.pop('limit', DEFAULT_PAGE_SIZE), 'limit')
    if page_size > MAX_PAGE_SIZE:
        raise UserError(f"You cannot request more than {MAX_PAGE_SIZE} cases per request.")

    query = (case_search.CaseSearchES()
             .domain(domain)
             .size(page_size)
             .sort("@indexed_on"))

    for key, val in params.items():
        if key.startswith(CUSTOM_PROPERTY_PREFIX):
            query = query.filter(_get_custom_property_filter(key, val))
        elif key == 'xpath':
            query = query.filter(_get_xpath_filter(domain, val))
        elif key in FILTERS:
            query = query.filter(FILTERS[key](val))
        else:
            raise UserError(f"'{key}' is not a valid parameter.")

    return query.run()


def _get_custom_property_filter(key, val):
    prop = key[len(CUSTOM_PROPERTY_PREFIX):]
    if val == "":
        return case_search.case_property_missing(prop)
    return case_search.exact_case_property_text_query(prop, val)


def _get_xpath_filter(domain, xpath):
    try:
        return build_filter_from_xpath(domain, xpath)
    except CaseFilterError as e:
        raise UserError(f'Bad XPath: {e}')
