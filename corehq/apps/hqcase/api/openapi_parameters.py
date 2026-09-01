"""The Case API v2 query parameters, as OpenAPI declarations.

The counterpart to ``openapi_docs.py``, which declares this API's request
and response *schemas*: this module declares its *query parameters*. Both
are documentation, and neither belongs in ``get_list.py``, whose job is
turning a request's parameters into an Elasticsearch query.

The filters themselves stay in ``get_list.py`` -- ``SIMPLE_FILTERS`` and
``COMPOUND_FILTERS`` are the query implementation, and are imported here to
be described. Splitting the description from the filter it describes is safe
because the two are tied together by a test, not by proximity:
``test_every_case_api_filter_has_a_description`` fails if a filter is added
without one, wherever the two happen to live.
"""

from corehq.apps.api.openapi.declarations import query_parameter

from .get_list import (
    COMPOUND_FILTERS,
    DEFAULT_PAGE_SIZE,
    INCLUDE_DEPRECATED,
    MAX_PAGE_SIZE,
    SIMPLE_FILTERS,
)

#: Public reference for the ``query`` parameter's expression syntax.
CASE_QUERY_LANGUAGE_URL = (
    'https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/'
    '2143949904/Case+Query+Language'
)

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

# The compound filters those qualifiers apply to: every entry built by
# ``get_list._make_date_filter()``. Named explicitly rather than assumed
# for anything not listed as freeform below -- publishing
# ``newfilter.gte`` for a filter that has no date qualifiers would
# document a parameter ``_get_filter()`` rejects, and nothing about the
# generated spec would look wrong.
# ``test_every_compound_filter_is_classified`` fails if this and
# FREEFORM_COMPOUND_FILTERS stop covering COMPOUND_FILTERS between them.
DATE_COMPOUND_FILTERS = frozenset({
    'last_modified',
    'server_last_modified',
    'date_opened',
    'date_closed',
    'indexed_on',
})

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
                       'cursor. Paging through with cursor returns '
                       'cases ordered oldest-indexed to newest-indexed; '
                       'a case that is updated while you are paging '
                       'through results may be skipped by the page it '
                       'would otherwise have appeared in and returned '
                       'again near the end of the results instead.',
        'schema': {'type': 'string'},
    },
    {
        'name': 'query',
        # The parser is build_filter_from_xpath() in
        # corehq/apps/case_search/filter_dsl.py; the published description
        # points at the public reference instead, which is where a caller
        # can actually look the syntax up.
        'description': 'A Case Query Language expression, filtering on '
                       'case properties and related cases -- for example '
                       '`case_type = "patient" and age > 30`. See '
                       f'{CASE_QUERY_LANGUAGE_URL} for the full syntax.',
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


def _filter_description(name):
    """``FILTER_DESCRIPTIONS[name]``, without the ability to take the
    site down.

    ``filter_parameters()`` runs at *import* time -- it is a decorator
    argument in ``corehq/apps/hqcase/views.py`` -- so an indexing lookup
    here would turn a filter added without a description into a
    ``KeyError`` during Django app loading, taking down the whole site
    rather than failing a test. ``tests/test_case_v2_docs.py``'s
    ``test_every_case_api_filter_has_a_description`` is the real gate on
    this invariant; a safe lookup here just keeps a violation from being
    worse than a test failure.
    """
    return FILTER_DESCRIPTIONS.get(name, f"Filter cases by '{name}'.")


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
        query_parameter(
            param['name'], param.get('description'), param.get('schema')
        )
        for param in NON_FILTER_PARAMETERS
    ]
    for name in sorted(SIMPLE_FILTERS):
        parameters.append(query_parameter(name, _filter_description(name)))
    for name in sorted(COMPOUND_FILTERS):
        parameters.extend(_compound_filter_parameters(name))
    return parameters


def _compound_filter_parameters(name):
    """The concrete query parameters one compound filter is published as.

    A compound filter's kind decides how its qualifier is spelled, and an
    unclassified filter is published under a placeholder rather than
    guessed at: naming a kind it does not have would document parameters
    the API rejects. Like ``_filter_description()``, this degrades instead
    of raising because ``filter_parameters()`` runs at import time, so a
    ``KeyError`` here would take the site down rather than fail a test --
    ``test_every_compound_filter_is_classified`` is the real gate.
    """
    description = _filter_description(name)
    if name in FREEFORM_COMPOUND_FILTERS:
        placeholder = FREEFORM_COMPOUND_FILTERS[name]
        return [query_parameter(f'{name}.<{placeholder}>', description)]
    if name in DATE_COMPOUND_FILTERS:
        return [
            query_parameter(f'{name}.{qualifier}', description)
            for qualifier in DATE_FILTER_QUALIFIERS
        ]
    return [query_parameter(f'{name}.<qualifier>', description)]
