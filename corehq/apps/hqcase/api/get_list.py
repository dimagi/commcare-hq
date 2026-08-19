from base64 import b64decode, b64encode

from django.http import QueryDict

from corehq.apps.api.util import make_date_filter
from corehq.apps.case_search.filter_dsl import (
    build_filter_from_xpath,
)
from corehq.apps.case_search.exceptions import CaseFilterError
from corehq.apps.es import case_search, filters
from corehq.apps.es import cases as case_es
from corehq.apps.reports.standard.cases.utils import (
    query_location_restricted_cases,
)
from corehq.apps.data_dictionary.util import get_data_dict_deprecated_case_types
from dimagi.utils.parsing import FALSE_STRINGS
from .core import UserError, serialize_es_case
from .field_filters import get_fields_filter_fn

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 5000
INDEXED_AFTER = 'indexed_on.gte'
LAST_CASE_ID = 'last_case_id'
INCLUDE_DEPRECATED = 'include_deprecated'


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

# Descriptions for the query parameters generated from the filters above.
FILTER_DESCRIPTIONS = {
    'external_id': 'Return cases with this external ID.',
    'case_type': 'Return cases of this case type.',
    'owner_id': 'Return cases owned by this user or group ID.',
    'case_name': 'Return cases with this case name.',
    'closed': 'Return only closed (true) or only open (false) cases.',
    INCLUDE_DEPRECATED: 'Include cases whose case type is deprecated.',
    'properties': 'Filter by case property, as properties.<name>=<value>.',
    'last_modified': 'Filter by modification date, as '
                     'last_modified.gte=<date>.',
    'server_last_modified': 'Filter by server modification date.',
    'date_opened': 'Filter by the date the case was opened.',
    'date_closed': 'Filter by the date the case was closed.',
    'indexed_on': 'Filter by the date the case was indexed for search.',
    'indices': 'Return cases indexed by the given case, as '
               'indices.<identifier>=<case_id>.',
}


# The date-based compound filters take one of exactly these qualifiers
# (see _make_date_filter/make_date_filter). Unlike ``properties`` and
# ``indices``, whose qualifier is an open-ended, caller-supplied name,
# this set is small and fixed, so each ``<name>.<qualifier>`` can be
# published as a concrete, usable parameter.
DATE_FILTER_QUALIFIERS = ('gt', 'gte', 'lt', 'lte')

# Compound filters whose qualifier is a caller-supplied name (a case
# property, or an index identifier) rather than one of a fixed set --
# there is no way to enumerate these as concrete parameters, so they are
# published under a documented placeholder name instead. OpenAPI 3.0.3
# has no first-class way to express "a family of parameters sharing a
# dotted prefix"; this matches the convention already used for these
# same filters on docs/api/cases-v2.rst.
FREEFORM_COMPOUND_FILTERS = {
    'properties': 'name',
    'indices': 'identifier',
}


# Parameters get_list() and its helpers accept that are not themselves
# case filters: paging (limit/cursor), a raw query expression, and the
# field-shaping parameters implemented by field_filters.py. Kept apart
# from FILTER_DESCRIPTIONS/SIMPLE_FILTERS/COMPOUND_FILTERS because they
# are not filters and are never looked up by name from those tables.
_FIELDS_DESCRIPTION = (
    'Comma-separated list of field names to include in the response. '
    'Use dot notation to select a nested field, e.g. '
    'fields.properties=<name>. Mutually exclusive with exclude -- using '
    'both in the same request returns an error.'
)
_EXCLUDE_DESCRIPTION = (
    'Comma-separated list of field names to remove from the response. '
    'Use dot notation to select a nested field, e.g. '
    'exclude.properties=<name>. Mutually exclusive with fields -- using '
    'both in the same request returns an error.'
)

NON_FILTER_PARAMETERS = (
    {
        'name': 'limit',
        'description': f'Maximum number of cases to return per page. '
                       f'Defaults to {DEFAULT_PAGE_SIZE}, maximum '
                       f'{MAX_PAGE_SIZE}.',
        'schema': {'type': 'integer', 'default': DEFAULT_PAGE_SIZE},
    },
    {
        'name': 'cursor',
        'description': "An opaque cursor from a previous response's "
                       '`next.cursor`, used to fetch the next page of '
                       'results. Do not combine with other filter '
                       'parameters, which are already encoded in the '
                       'cursor.',
        'schema': {'type': 'string'},
    },
    {
        'name': 'query',
        'description': 'An XPath-like case search query expression '
                       '(see build_filter_from_xpath).',
        'schema': {'type': 'string'},
    },
    {
        'name': 'fields',
        'description': _FIELDS_DESCRIPTION,
        'schema': {'type': 'string'},
    },
    {
        'name': 'fields.<name>',
        'description': _FIELDS_DESCRIPTION,
        'schema': {'type': 'string'},
    },
    {
        'name': 'exclude',
        'description': _EXCLUDE_DESCRIPTION,
        'schema': {'type': 'string'},
    },
    {
        'name': 'exclude.<name>',
        'description': _EXCLUDE_DESCRIPTION,
        'schema': {'type': 'string'},
    },
)


def filter_parameters():
    """OpenAPI query parameters this endpoint accepts: the case filters
    plus paging, the raw query expression, and the field-shaping
    parameters (see ``NON_FILTER_PARAMETERS``).

    None of ``SIMPLE_FILTERS`` or ``COMPOUND_FILTERS`` names a usable
    query parameter on its own for a compound filter: ``_get_filter()``
    requires a ``.`` in the key, so ``GET ...?properties=x`` is rejected
    with "'properties' is not a valid parameter." Each compound filter is
    therefore expanded into the concrete parameter name(s) a client can
    actually send.
    """
    parameters = [
        {'in': 'query', 'required': False, **param}
        for param in NON_FILTER_PARAMETERS
    ]
    for name in sorted(SIMPLE_FILTERS):
        parameters.append({
            'name': name,
            'in': 'query',
            'required': False,
            'description': FILTER_DESCRIPTIONS[name],
            'schema': {'type': 'string'},
        })
    for name in sorted(COMPOUND_FILTERS):
        if name in FREEFORM_COMPOUND_FILTERS:
            placeholder = FREEFORM_COMPOUND_FILTERS[name]
            parameters.append({
                'name': f'{name}.<{placeholder}>',
                'in': 'query',
                'required': False,
                'description': FILTER_DESCRIPTIONS[name],
                'schema': {'type': 'string'},
            })
        else:
            for qualifier in DATE_FILTER_QUALIFIERS:
                parameters.append({
                    'name': f'{name}.{qualifier}',
                    'in': 'query',
                    'required': False,
                    'description': FILTER_DESCRIPTIONS[name],
                    'schema': {'type': 'string'},
                })
    return parameters


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
    filter_fields = get_fields_filter_fn(params)
    ret = {
        "matching_records": es_result.total,
        "cases": [filter_fields(serialize_es_case(case)) for case in hits],
    }

    cases_in_result = len(hits)
    limit = query._size or MAX_PAGE_SIZE
    if cases_in_result == limit:
        last_date, last_id = es_result.raw_hits[-1]['sort']
        params.update({
            INDEXED_AFTER: last_date,
            LAST_CASE_ID: last_id
        })
        cursor = params.urlencode()
        ret['next'] = {'cursor': b64encode(cursor.encode('utf-8'))}

    return ret


def _get_cursor_query(domain, params, last_date, last_id):
    query = _get_query(domain, params)
    query = query.search_after(last_date, last_id)
    return query


def _get_query(domain, params):
    page_size = _to_int(params.get('limit', DEFAULT_PAGE_SIZE), 'limit')
    if page_size > MAX_PAGE_SIZE:
        raise UserError(f"You cannot request more than {MAX_PAGE_SIZE} cases per request.")
    query = (case_search.CaseSearchES()
             .domain(domain)
             .size(page_size))
    query = query.sort('@indexed_on').sort('doc_id', reset_sort=False)
    for key, val in params.lists():
        if _is_handled_elsewhere(key):
            continue
        if len(val) == 1:
            query = query.filter(_get_filter(domain, key, val[0]))
        else:
            # e.g. key='owner_id', val=['abc123', 'def456']
            filter_list = [_get_filter(domain, key, v) for v in val]
            query = query.filter(filters.OR(*filter_list))
    return query


def _is_handled_elsewhere(key):
    return (
        key in ('limit', 'fields', 'exclude')
        or key.startswith(('fields.', 'exclude.'))
    )


def _get_filter(domain, key, val):
    if key == 'query':
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
        return build_filter_from_xpath(query, domain=domain)
    except CaseFilterError as e:
        raise UserError(f'Bad query: {e}')
