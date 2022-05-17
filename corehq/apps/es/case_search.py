"""
CaseSearchES
------

.. code-block:: python

from corehq.apps.es import case_search as case_search_es

    q = (case_search_es.CaseSearchES()
         .domain('testproject')
"""

from warnings import warn

from django.conf import settings
from django.utils.dateparse import parse_date
from memoized import memoized

from corehq.apps.case_search.const import (
    CASE_PROPERTIES_PATH,
    IDENTIFIER,
    INDEXED_ON,
    INDICES_PATH,
    IS_RELATED_CASE,
    REFERENCED_ID,
    RELEVANCE_SCORE,
    SPECIAL_CASE_PROPERTIES,
    SPECIAL_CASE_PROPERTIES_MAP,
    SYSTEM_PROPERTIES,
    VALUE,
)
from corehq.apps.es.cases import CaseES, owner
from corehq.util.dates import iso_string_to_datetime

from . import filters, queries
from .cases import ElasticCase
from .client import ElasticDocumentAdapter
from .transient_util import get_adapter_mapping, from_dict_with_possible_id


class CaseSearchES(CaseES):
    index = "case_search"

    @property
    def builtin_filters(self):
        return [
            case_property_filter,
            blacklist_owner_id,
            external_id,
            indexed_on,
            case_property_missing,
        ] + super(CaseSearchES, self).builtin_filters

    def case_property_query(self, case_property_name, value, clause=queries.MUST, fuzzy=False):
        """
        Search for all cases where case property with name `case_property_name`` has text value `value`

        Usage: (CaseSearchES()
                .domain('swashbucklers')
                .case_property_query("name", "rebdeard", "must", fuzzy=True)
                .case_property_query("age", "15", "must")
                .case_property_query("has_parrot", "yes", "should")
                .case_property_query("is_pirate", "yes", "must_not"))

        Can be chained with regular filters . Running a set_query after this will destroy it.
        Clauses can be any of SHOULD, MUST, or MUST_NOT
        """
        return self.add_query(case_property_query(case_property_name, value, fuzzy), clause)

    def regexp_case_property_query(self, case_property_name, regex, clause=queries.MUST):
        """
        Search for all cases where case property `case_property_name` matches the regular expression in `regex`
        """
        return self.add_query(
            _base_property_query(case_property_name, queries.regexp(
                "{}.{}".format(CASE_PROPERTIES_PATH, VALUE), regex)
            ),
            clause,
        )

    def numeric_range_case_property_query(self, case_property_name, gt=None,
                                          gte=None, lt=None, lte=None, clause=queries.MUST):
        """
        Search for all cases where case property `case_property_name` fulfills the range criteria.
        """
        return self.add_query(
            case_property_range_query(case_property_name, gt, gte, lt, lte),
            clause
        )

    def xpath_query(self, domain, xpath, fuzzy=False):
        """Search for cases using an XPath predicate expression.

        Enter an arbitrary XPath predicate in the context of the case. Also supports related case lookups.
        e.g you can do things like:

        - case properties: "first_name = 'dolores' and last_name = 'abernathy'"
        - date ranges: "first_came_online >= '2017-08-12' or died <= '2020-11-15"
        - numeric ranges: "age >= 100 and height < 1.25"
        - related cases: "mother/first_name = 'maeve' or parent/parent/host/age = 13"

        If fuzzy is true, all equality checks will be treated as fuzzy.
        """
        from corehq.apps.case_search.filter_dsl import build_filter_from_xpath
        return self.filter(build_filter_from_xpath(domain, xpath, fuzzy=fuzzy))

    def get_child_cases(self, case_ids, identifier):
        """Returns all cases that reference cases with ids: `case_ids`
        """
        if isinstance(case_ids, str):
            case_ids = [case_ids]

        return self.add_query(
            reverse_index_case_query(case_ids, identifier),
            queries.MUST,
        )

    def sort_by_case_property(self, case_property_name, desc=False):
        sort_filter = filters.term("{}.key.exact".format(CASE_PROPERTIES_PATH), case_property_name)
        return self.nested_sort(
            CASE_PROPERTIES_PATH, "{}.{}".format(VALUE, 'numeric'),
            sort_filter,
            desc,
            reset_sort=True
        ).nested_sort(
            CASE_PROPERTIES_PATH, "{}.{}".format(VALUE, 'date'),
            sort_filter,
            desc,
            reset_sort=False
        ).nested_sort(
            CASE_PROPERTIES_PATH, "{}.{}".format(VALUE, 'exact'),
            sort_filter,
            desc,
            reset_sort=False
        )


class ElasticCaseSearch(ElasticDocumentAdapter):

    _index_name = getattr(settings, "ES_CASE_SEARCH_INDEX_NAME", "case_search_2018-05-29")
    type = ElasticCase.type

    @property
    def mapping(self):
        return get_adapter_mapping(self)

    @classmethod
    def from_python(cls, doc):
        return from_dict_with_possible_id(doc)


def case_property_filter(case_property_name, value):
    warn("Use the query versions of this function from the case_search module instead", DeprecationWarning)
    return filters.nested(
        CASE_PROPERTIES_PATH,
        filters.AND(
            filters.term("{}.key.exact".format(CASE_PROPERTIES_PATH), case_property_name),
            filters.term("{}.{}".format(CASE_PROPERTIES_PATH, VALUE), value),
        )
    )


def case_property_query(case_property_name, value, fuzzy=False, multivalue_mode=None):
    """
    Search for all cases where case property with name `case_property_name`` has text value `value`
    """
    if value is None:
        raise TypeError("You cannot pass 'None' as a case property value")
    if multivalue_mode not in ['and', 'or', None]:
        raise ValueError(" 'mode' must be one of: 'and', 'or', None")
    if value == '':
        return case_property_missing(case_property_name)
    if fuzzy:
        return filters.OR(
            # fuzzy match
            case_property_text_query(case_property_name, value, fuzziness='AUTO', operator=multivalue_mode),
            # non-fuzzy match. added to improve the score of exact matches
            case_property_text_query(case_property_name, value, operator=multivalue_mode),
        )
    if not fuzzy and multivalue_mode in ['or', 'and']:
        return case_property_text_query(case_property_name, value, operator=multivalue_mode)
    return exact_case_property_text_query(case_property_name, value)


def exact_case_property_text_query(case_property_name, value):
    """Filter by case property.

    This performs an exact match on the value in the case property, including
    letter casing and punctuation.

    """
    return queries.nested(
        CASE_PROPERTIES_PATH,
        queries.filtered(
            queries.match_all(),
            filters.AND(
                filters.term('{}.key.exact'.format(CASE_PROPERTIES_PATH), case_property_name),
                filters.term('{}.{}.exact'.format(CASE_PROPERTIES_PATH, VALUE), value),
            )
        )
    )


def case_property_text_query(case_property_name, value, fuzziness='0', operator=None):
    """Filter by case_properties.key and do a text search in case_properties.value

    This does not do exact matches on the case property value. If the value has
    multiple words, they will be OR'd together in this query. You may want to
    use the `exact_case_property_text_query` instead.

    """
    return _base_property_query(
        case_property_name,
        queries.match(value, '{}.{}'.format(CASE_PROPERTIES_PATH, VALUE), fuzziness=fuzziness, operator=operator)
    )


def case_property_range_query(case_property_name, gt=None, gte=None, lt=None, lte=None):
    """Returns cases where case property `key` fall into the range provided.

    """
    kwargs = {'gt': gt, 'gte': gte, 'lt': lt, 'lte': lte}
    # if its a number, use it
    try:
        # numeric range
        kwargs = {key: float(value) for key, value in kwargs.items() if value is not None}
        return _base_property_query(
            case_property_name,
            queries.range_query("{}.{}.numeric".format(CASE_PROPERTIES_PATH, VALUE), **kwargs)
        )
    except ValueError:
        pass

    # if its a date, use it
    # date range
    kwargs = {
        key: parse_date(value) for key, value in kwargs.items()
        if value is not None and parse_date(value) is not None
    }
    if not kwargs:
        raise TypeError()       # Neither a date nor number was passed in

    return _base_property_query(
        case_property_name,
        queries.date_range("{}.{}.date".format(CASE_PROPERTIES_PATH, VALUE), **kwargs)
    )


def reverse_index_case_query(case_ids, identifier=None):
    """Fetches related cases related by `identifier`.

    For example, in a regular parent/child relationship, given a list of parent
    case ids, this will return all the child cases which point to the parents
    with identifier `parent`.

    """
    if isinstance(case_ids, str):
        case_ids = [case_ids]

    if identifier is None:      # some old relationships don't have an identifier specified
        f = filters.term('{}.{}'.format(INDICES_PATH, REFERENCED_ID), list(case_ids)),
    else:
        f = filters.AND(
            filters.term('{}.{}'.format(INDICES_PATH, REFERENCED_ID), list(case_ids)),
            filters.term('{}.{}'.format(INDICES_PATH, IDENTIFIER), identifier),
        )
    return queries.nested(
        INDICES_PATH,
        queries.filtered(
            queries.match_all(),
            f
        )
    )


def case_property_not_set(case_property_name):
    return filters.NOT(
        queries.nested(
            CASE_PROPERTIES_PATH,
            queries.filtered(
                queries.match_all(),
                filters.term('{}.key.exact'.format(CASE_PROPERTIES_PATH), case_property_name),
            )
        )
    )


def case_property_missing(case_property_name):
    """case_property_name isn't set or is the empty string

    """
    return filters.OR(
        case_property_not_set(case_property_name),
        exact_case_property_text_query(case_property_name, '')
    )


def case_property_geo_distance(geopoint_property_name, geopoint, **kwargs):
    return _base_property_query(
        geopoint_property_name,
        queries.geo_distance(f"{CASE_PROPERTIES_PATH}.geopoint_value", geopoint, **kwargs)
    )


def _base_property_query(case_property_name, query):
    return queries.nested(
        CASE_PROPERTIES_PATH,
        queries.filtered(
            query,
            filters.term('{}.key.exact'.format(CASE_PROPERTIES_PATH), case_property_name)
        )
    )


def blacklist_owner_id(owner_id):
    return filters.NOT(owner(owner_id))


def external_id(external_id):
    return filters.term('external_id', external_id)


def indexed_on(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range(INDEXED_ON, gt, gte, lt, lte)


def flatten_result(hit, include_score=False, is_related_case=False):
    """Flattens a result from CaseSearchES into the format that Case serializers
    expect

    i.e. instead of {'name': 'blah', 'case_properties':{'key':'foo', 'value':'bar'}} we return
    {'name': 'blah', 'foo':'bar'}

    Note that some dynamic case properties, if present, will overwrite
    internal case properties:

        domain
        type
        opened_on
        opened_by
        modified_on
        server_modified_on
        modified_by         -> also overwrites user_id
        closed
        closed_on
        closed_by
        deleted
        deleted_on
        deletion_id
    """
    try:
        result = hit['_source']
    except KeyError:
        result = hit

    if include_score:
        result[RELEVANCE_SCORE] = hit['_score']
    if is_related_case:
        result[IS_RELATED_CASE] = "true"
    case_properties = result.pop(CASE_PROPERTIES_PATH, [])
    for case_property in case_properties:
        key = case_property.get('key')
        value = case_property.get('value')
        if key is not None and key not in SPECIAL_CASE_PROPERTIES and value:
            result[key] = value

    for key in SYSTEM_PROPERTIES:
        result.pop(key, None)
    return result


def wrap_case_search_hit(hit, include_score=False, is_related_case=False):
    """Convert case search index hit to CommCareCase

    Nearly the opposite of
    `corehq.pillows.case_search.transform_case_for_elasticsearch`.

    The "case_properties" list of key/value pairs is converted to a dict
    and assigned to `case_json`. 'Secial' case properties are excluded
    from `case_json`, even if they were present in the original case's
    dynamic properties.

    All fields excluding "case_properties" and its contents are assigned
    as attributes on the case object if `CommCareCase` has a field
    with a matching name. Fields like "doc_type" and "@indexed_on" are
    ignored.

    Warning: `include_score=True` or `is_related_case=True` may cause
    the relevant user-defined properties to be overwritten.

    :returns: A `CommCareCase` instance.
    """
    from corehq.form_processor.models import CommCareCase
    data = hit.get("_source", hit)
    _SPECIAL_PROPERTIES = SPECIAL_CASE_PROPERTIES_MAP
    _VALUE = VALUE
    case = CommCareCase(
        case_id=data.get("_id", None),
        case_json={
            prop["key"]: prop[_VALUE]
            for prop in data.get(CASE_PROPERTIES_PATH, {})
            if prop["key"] not in _SPECIAL_PROPERTIES
        },
        indices=data.get("indices", []),
    )
    _CONVERSIONS = CONVERSIONS
    _setattr = setattr
    case_fields = _case_fields()
    for key, value in data.items():
        if key in case_fields:
            if value is not None and key in _CONVERSIONS:
                value = _CONVERSIONS[key](value)
            _setattr(case, key, value)
    if include_score:
        case.case_json[RELEVANCE_SCORE] = hit['_score']
    if is_related_case:
        case.case_json[IS_RELATED_CASE] = "true"
    return case


@memoized
def _case_fields():
    from corehq.form_processor.models import CommCareCase
    fields = {f.attname for f in CommCareCase._meta.concrete_fields}
    fields.add("user_id")  # synonym for "modified_by"
    return fields


CONVERSIONS = {
    "closed_on": iso_string_to_datetime,
    "modified_on": iso_string_to_datetime,
    "opened_on": iso_string_to_datetime,
    "server_modified_on": iso_string_to_datetime,
    "closed_on": iso_string_to_datetime,
}
