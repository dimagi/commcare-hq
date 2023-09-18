from base64 import b64decode, b64encode

from django.http import QueryDict

from corehq.apps.api.util import make_date_filter
from corehq.apps.case_search.const import CASE_PROPERTIES_PATH
from corehq.apps.case_search.filter_dsl import (
    build_filter_from_xpath,
)
from corehq.apps.case_search.exceptions import CaseFilterError
from corehq.apps.es import case_search, filters, queries
from corehq.apps.es import cases as case_es
from corehq.apps.reports.standard.cases.utils import (
    query_location_restricted_cases,
)
from corehq.apps.data_dictionary.util import get_data_dict_deprecated_case_types
from dimagi.utils.parsing import FALSE_STRINGS
from .core import UserError, serialize_es_case

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 5000
INDEXED_AFTER = 'indexed_on.gte'
LAST_CASE_ID = 'last_case_id'
INCLUDE_DEPRECATED = 'include_deprecated'

# This is not how sorting is typically done - sorting by the _id field causes
# timeouts for reasons we don't quite understand. Until that's resolved,
# sorting by case_properties.@case_id seems to work fine.
_SORTING_BLOCK = [{
    '@indexed_on': {'order': 'asc'},
    'case_properties.value.exact': {
        'order': 'asc',
        'nested_path': 'case_properties',
        'nested_filter': {'term': {"case_properties.key.exact": "@case_id"}},
    }
}]


def _to_boolean(val):
    return not (val == '' or val.lower() in FALSE_STRINGS)


def _to_int(val, param_name):
    try:
        return int(val)
    except ValueError:
        raise UserError(f"'{val}' is not a valid value for '{param_name}'")


def _make_date_filter(date_filter):
    filter_fn = make_date_filter(date_filter)

    def _exception_converter(param, value):
        """Wrapper to convert ValueError to UserError"""
        try:
            return filter_fn(param, value)
        except ValueError as e:
            raise UserError(str(e))

    return _exception_converter


def _include_deprecated_filter(domain, include_deprecated):
    if _to_boolean(include_deprecated):
        return filters.match_all()
    deprecated_case_types = get_data_dict_deprecated_case_types(domain)
    return filters.NOT(filters.term('type.exact', deprecated_case_types))


def _index_filter(identifier, case_id):
    return case_search.reverse_index_case_query(case_id, identifier)


SIMPLE_FILTERS = {
    'external_id': case_search.external_id,
    'case_type': case_es.case_type,
    'owner_id': case_es.owner,
    'case_name': case_es.case_name,
    'closed': lambda val: case_es.is_closed(_to_boolean(val)),
    INCLUDE_DEPRECATED: _include_deprecated_filter,
}

# Compound filters take the form `prefix.qualifier=value`
# These filter functions are called with qualifier and value
COMPOUND_FILTERS = {
    'properties': case_search.case_property_query,
    'last_modified': _make_date_filter(case_es.modified_range),
    'server_last_modified': _make_date_filter(case_es.server_modified_range),
    'date_opened': _make_date_filter(case_es.opened_range),
    'date_closed': _make_date_filter(case_es.closed_range),
    'indexed_on': _make_date_filter(case_search.indexed_on),
    'indices': _index_filter,
}


def get_list(domain, couch_user, params):
    if 'cursor' in params:
        params_string = b64decode(params['cursor']).decode('utf-8')
        params = QueryDict(params_string, mutable=True)
        # QueryDict.pop() returns a list
        last_date = params.pop(INDEXED_AFTER, [None])[0]
        last_id = params.pop(LAST_CASE_ID, [None])[0]
        query = _get_cursor_query(domain, params, last_date, last_id)
    else:
        params = params.copy()  # Makes params mutable for pagination below
        query = _get_query(domain, params)

    if not couch_user.has_permission(domain, 'access_all_locations'):
        query = query_location_restricted_cases(query, domain, couch_user)

    es_result = query.run()
    hits = es_result.hits
    ret = {
        "matching_records": es_result.total,
        "cases": [serialize_es_case(case) for case in hits],
    }

    cases_in_result = len(hits)
    if cases_in_result and es_result.total > cases_in_result:
        params.update({
            INDEXED_AFTER: hits[-1]["@indexed_on"],
            LAST_CASE_ID: hits[-1]["_id"],
        })
        cursor = params.urlencode()
        ret['next'] = {'cursor': b64encode(cursor.encode('utf-8'))}

    return ret


def _get_cursor_query(domain, params, last_date, last_id):
    query = _get_query(domain, params)
    id_filter = queries.nested(
        CASE_PROPERTIES_PATH,
        filters.AND(
            filters.term(case_search.PROPERTY_KEY, '@case_id'),
            filters.range_filter(case_search.PROPERTY_VALUE_EXACT, gt=last_id),
        )
    )
    return query.filter(
        filters.OR(
            filters.AND(
                filters.term('@indexed_on', last_date),
                id_filter,
            ),
            case_search.indexed_on(gt=last_date),
        )
    )


def _get_query(domain, params):
    page_size = _to_int(params.get('limit', DEFAULT_PAGE_SIZE), 'limit')
    if page_size > MAX_PAGE_SIZE:
        raise UserError(f"You cannot request more than {MAX_PAGE_SIZE} cases per request.")
    query = (case_search.CaseSearchES()
             .domain(domain)
             .size(page_size))
    query.es_query['sort'] = _SORTING_BLOCK  # unorthodox, see comment above
    for key, val in params.lists():
        if len(val) == 1:
            query = query.filter(_get_filter(domain, key, val[0]))
        else:
            # e.g. key='owner_id', val=['abc123', 'def456']
            filter_list = [_get_filter(domain, key, v) for v in val]
            query = query.filter(filters.OR(*filter_list))
    return query


def _get_filter(domain, key, val):
    if key == 'limit':
        return filters.match_all()
    elif key == 'query':
        return _get_query_filter(domain, val)
    elif key in SIMPLE_FILTERS:
        if key == INCLUDE_DEPRECATED:
            return SIMPLE_FILTERS[key](domain, val)
        return SIMPLE_FILTERS[key](val)
    elif '.' in key and key.split(".")[0] in COMPOUND_FILTERS:
        prefix, qualifier = key.split(".", maxsplit=1)
        return COMPOUND_FILTERS[prefix](qualifier, val)
    else:
        raise UserError(f"'{key}' is not a valid parameter.")


def _get_query_filter(domain, query):
    try:
        return build_filter_from_xpath(domain, query)
    except CaseFilterError as e:
        raise UserError(f'Bad query: {e}')
