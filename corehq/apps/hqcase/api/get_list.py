from base64 import b64decode, b64encode

from django.http import QueryDict
from django.utils.http import urlencode

from corehq.apps.api.util import make_date_filter
from corehq.apps.case_search.filter_dsl import (
    CaseFilterError,
    build_filter_from_xpath,
)
from corehq.apps.es import case_search
from corehq.apps.es import cases as case_es
from dimagi.utils.parsing import FALSE_STRINGS
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


def _get_custom_property_filter(case_property, val):
    if val == "":
        return case_search.case_property_missing(case_property)
    return case_search.exact_case_property_text_query(case_property, val)


def _make_date_filter(date_filter):
    filter_fn = make_date_filter(date_filter)

    def _exception_converter(param, value):
        """Wrapper to convert ValueError to UserError"""
        try:
            return filter_fn(param, value)
        except ValueError as e:
            raise UserError(str(e))

    return _exception_converter


def _index_filter(identifier, case_id):
    return case_search.reverse_index_case_query(case_id, identifier)


SIMPLE_FILTERS = {
    'external_id': case_search.external_id,
    'case_type': case_es.case_type,
    'owner_id': case_es.owner,
    'case_name': case_es.case_name,
    'closed': lambda val: case_es.is_closed(_to_boolean(val)),
}

# Compound filters take the form `prefix.qualifier=value`
# These filter functions are called with qualifier and value
COMPOUND_FILTERS = {
    'property': _get_custom_property_filter,
    'last_modified': _make_date_filter(case_es.modified_range),
    'server_last_modified': _make_date_filter(case_es.server_modified_range),
    'date_opened': _make_date_filter(case_es.opened_range),
    'date_closed': _make_date_filter(case_es.closed_range),
    'indexed_on': _make_date_filter(case_search.indexed_on),
    'indices': _index_filter,
}


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
        if key == 'xpath':
            query = query.filter(_get_xpath_filter(domain, val))
        elif key in SIMPLE_FILTERS:
            query = query.filter(SIMPLE_FILTERS[key](val))
        elif '.' in key and key.split(".")[0] in COMPOUND_FILTERS:
            prefix, qualifier = key.split(".", maxsplit=1)
            query = query.filter(COMPOUND_FILTERS[prefix](qualifier, val))
        else:
            raise UserError(f"'{key}' is not a valid parameter.")

    return query.run()


def _get_xpath_filter(domain, xpath):
    try:
        return build_filter_from_xpath(domain, xpath)
    except CaseFilterError as e:
        raise UserError(f'Bad XPath: {e}')
