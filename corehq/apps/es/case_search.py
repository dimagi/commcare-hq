"""
CaseSearchES
------

.. code-block:: python

from corehq.apps.es import case_search as case_search_es

    q = (case_search_es.CaseSearchES()
         .domain('testproject')
"""

from copy import deepcopy
from datetime import datetime

from django.conf import settings

from memoized import memoized

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.case_search.const import (
    CASE_PROPERTIES_PATH,
    GEOPOINT_VALUE,
    IDENTIFIER,
    INDEXED_ON,
    INDICES_PATH,
    REFERENCED_ID,
    RELEVANCE_SCORE,
    INDEXED_METADATA_BY_KEY,
    VALUE,
)
from corehq.apps.es.cases import CaseES, owner
from corehq.apps.es.transient_util import doc_adapter_from_cname
from corehq.util.dates import iso_string_to_datetime

from . import filters, queries
from .cases import case_adapter
from .client import BulkActionItem, ElasticDocumentAdapter, create_document_adapter
from .const import (
    HQ_CASE_SEARCH_INDEX_CANONICAL_NAME,
    HQ_CASE_SEARCH_INDEX_NAME,
    HQ_CASE_SEARCH_SECONDARY_INDEX_NAME,
)
from .index.analysis import PHONETIC_ANALYSIS
from .index.settings import IndexSettingsKey

PROPERTY_KEY = f'{CASE_PROPERTIES_PATH}.key.exact'
PROPERTY_VALUE = f'{CASE_PROPERTIES_PATH}.{VALUE}'
PROPERTY_VALUE_EXACT = f'{CASE_PROPERTIES_PATH}.{VALUE}.exact'
PROPERTY_GEOPOINT_VALUE = f'{CASE_PROPERTIES_PATH}.{GEOPOINT_VALUE}'


class CaseSearchES(CaseES):
    index = HQ_CASE_SEARCH_INDEX_CANONICAL_NAME

    @property
    def builtin_filters(self):
        return [
            blacklist_owner_id,
            external_id,
            indexed_on,
            case_property_missing,
            filters.geo_bounding_box,
            filters.geo_polygon,
            filters.geo_shape,  # Available in Elasticsearch 8+
            filters.geo_grid,  # Available in Elasticsearch 8+
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
        from corehq.apps.case_search.filter_dsl import build_filter_from_xpath, SearchFilterContext
        context = SearchFilterContext(domain, fuzzy=fuzzy)
        return self.filter(build_filter_from_xpath(xpath, context=context))

    def get_child_cases(self, case_ids, identifier):
        """Returns all cases that reference cases with ids: `case_ids`
        """
        if isinstance(case_ids, str):
            case_ids = [case_ids]

        return self.add_query(
            reverse_index_case_query(case_ids, identifier),
            queries.MUST,
        )

    def sort_by_case_property(self, case_property_name, desc=False, sort_type=None):
        sort_filter = filters.term(PROPERTY_KEY, case_property_name)
        if sort_type:
            sort_missing = '_last' if desc else '_first'
            return self.nested_sort(
                CASE_PROPERTIES_PATH, "{}.{}".format(VALUE, sort_type),
                sort_filter,
                desc,
                reset_sort=False,
                sort_missing=sort_missing
            )

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

    analysis = PHONETIC_ANALYSIS
    settings_key = IndexSettingsKey.CASE_SEARCH
    canonical_name = HQ_CASE_SEARCH_INDEX_CANONICAL_NAME

    @property
    def mapping(self):
        from .mappings.case_search_mapping import CASE_SEARCH_MAPPING
        return CASE_SEARCH_MAPPING

    @property
    def model_cls(self):
        from corehq.form_processor.models.cases import CommCareCase
        return CommCareCase

    def _from_dict(self, case):
        """
        Takes in a dict which is result of ``CommCareCase.to_json``
        and applies required transformation to make it suitable for ES.

        :param case: an instance of ``dict`` which is ``case.to_json()``
        """
        from corehq.pillows.case_search import _get_case_properties

        case_dict = deepcopy(case)
        doc = {
            desired_property: case_dict.get(desired_property)
            for desired_property in self.mapping['properties'].keys()
            if desired_property != CASE_PROPERTIES_PATH
        }
        doc[INDEXED_ON] = json_format_datetime(datetime.utcnow())
        doc['case_properties'] = _get_case_properties(case_dict)
        doc['_id'] = case_dict['_id']
        return super()._from_dict(doc)

    def _get_domain_from_doc(self, doc):
        """
        `doc` can be CommcCareCase instance or dict. This util method extracts domain from doc.
        This will fail hard if domain is not present in doc.
        """
        if isinstance(doc, dict):
            return doc["domain"]
        if hasattr(doc, 'domain'):
            return doc.domain

    def index(self, doc, refresh=False):
        """
        Selectively multiplexes writes to a sub index based on the domain of the doc.
        """
        sub_index_adapter = multiplex_to_adapter(self._get_domain_from_doc(doc))
        if sub_index_adapter:
            # If we get a valid sub index adapter then we multiplex writes
            doc_obj = BulkActionItem.index(doc)
            payload = [self._render_bulk_action(doc_obj), sub_index_adapter._render_bulk_action(doc_obj)]
            return self._bulk(payload, refresh=refresh, raise_errors=True)
        # If adapter is None then simply index the docs
        super().index(doc, refresh=refresh)

    def bulk(self, actions, refresh=False, raise_errors=True):
        """
        Iterates over the list of actions and multiplexes writes to a sub index based on the domain of the doc.
        """
        payload = []
        for action in actions:
            payload.append(self._render_bulk_action(action))
            adapter = multiplex_to_adapter(self._get_domain_from_doc(action.doc))
            if adapter:
                payload.append(adapter._render_bulk_action(action))
        return self._bulk(payload, refresh=refresh, raise_errors=raise_errors)


case_search_adapter = create_document_adapter(
    ElasticCaseSearch,
    HQ_CASE_SEARCH_INDEX_NAME,
    case_adapter.type,
    secondary=HQ_CASE_SEARCH_SECONDARY_INDEX_NAME,
)


def multiplex_to_adapter(domain):
    """
    Reads `CASE_SEARCH_SUB_INDICES` from settings to see if we should multiplex writes for case_search index.
    Returns the appropriate adapter based on the domain passed.
    """
    multiplex_info = settings.CASE_SEARCH_SUB_INDICES
    domain_multiplex_settings = multiplex_info.get(domain, None)
    if domain_multiplex_settings and domain_multiplex_settings.get('multiplex_writes'):
        return doc_adapter_from_cname(domain_multiplex_settings['index_cname'])
    return None


def case_property_query(case_property_name, value, fuzzy=False, multivalue_mode=None, boost_first=False):
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
        return _base_property_query(
            case_property_name,
            filters.OR(
                # fuzzy match. This portion of this query OR's together multi-word case
                # property values and doesn't respect multivalue_mode
                queries.fuzzy(value, PROPERTY_VALUE, fuzziness='AUTO', prefix_length=2),
                # non-fuzzy match. added to improve the score of exact matches
                queries.match(value, PROPERTY_VALUE, operator=multivalue_mode)
            ),
        )
    if boost_first:
        return _base_property_query(
            case_property_name,
            filters.OR(
                filters.term(PROPERTY_VALUE, value),
                queries.match(value[0], PROPERTY_VALUE)
            )

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
                filters.term(PROPERTY_KEY, case_property_name),
                filters.term(PROPERTY_VALUE_EXACT, value),
            )
        )
    )


def case_property_text_query(case_property_name, value, operator=None):
    """Filter by case_properties.key and do a text search in case_properties.value

    This does not do exact matches on the case property value. If the value has
    multiple words, they will be OR'd together in this query. You may want to
    use the `exact_case_property_text_query` instead.

    """
    return _base_property_query(
        case_property_name,
        queries.match(value, PROPERTY_VALUE, operator=operator)
    )


def sounds_like_text_query(case_property_name, value):
    return _base_property_query(
        case_property_name,
        queries.match(value, '{}.{}.phonetic'.format(CASE_PROPERTIES_PATH, VALUE))
    )


def case_property_starts_with(case_property_name, value):
    """Filter by case_properties.key and do a text search in case_properties.value that
       matches starting substring.

    """
    return queries.nested(
        CASE_PROPERTIES_PATH,
        filters.AND(
            filters.term(PROPERTY_KEY, case_property_name),
            filters.prefix(PROPERTY_VALUE_EXACT, value),
        )
    )


def case_property_numeric_range(case_property_name, gt=None, gte=None, lt=None, lte=None):
    kwargs = {'gt': gt, 'gte': gte, 'lt': lt, 'lte': lte}
    return _base_property_query(
        case_property_name,
        queries.range_query("{}.{}.numeric".format(CASE_PROPERTIES_PATH, VALUE), **kwargs)
    )


def case_property_date_range(case_property_name, gt=None, gte=None, lt=None, lte=None):
    kwargs = {'gt': gt, 'gte': gte, 'lt': lt, 'lte': lte}
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


def _case_property_not_set(case_property_name):
    return filters.NOT(
        queries.nested(
            CASE_PROPERTIES_PATH,
            filters.term(PROPERTY_KEY, case_property_name),
        )
    )


def case_property_missing(case_property_name):
    """case_property_name isn't set or is the empty string"""
    return filters.OR(
        _case_property_not_set(case_property_name),
        exact_case_property_text_query(case_property_name, '')
    )


def case_property_geo_distance(geopoint_property_name, geopoint, **kwargs):
    return _base_property_query(
        geopoint_property_name,
        queries.geo_distance(PROPERTY_GEOPOINT_VALUE, geopoint, **kwargs)
    )


def _base_property_query(case_property_name, query):
    return queries.nested(
        CASE_PROPERTIES_PATH,
        queries.filtered(
            query,
            filters.term(PROPERTY_KEY, case_property_name)
        )
    )


def blacklist_owner_id(owner_id):
    return filters.NOT(owner(owner_id))


def external_id(external_id):
    return filters.term('external_id', external_id)


def indexed_on(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range(INDEXED_ON, gt, gte, lt, lte)


def wrap_case_search_hit(hit, include_score=False):
    """Convert case search index hit to CommCareCase

    Nearly the opposite of
    `corehq.apps.es.case_search.ElasticCaseSearch._from_dict`.

    The "case_properties" list of key/value pairs is converted to a dict
    and assigned to `case_json`. 'Special' case properties are excluded
    from `case_json`, even if they were present in the original case's
    dynamic properties, except of the COMMCARE_CASE_COPY_PROPERTY_NAME
    property.

    All fields excluding "case_properties" and its contents are assigned
    as attributes on the case object if `CommCareCase` has a field
    with a matching name. Fields like "doc_type" and "@indexed_on" are
    ignored.

    Warning: `include_score=True` may cause
    the relevant user-defined properties to be overwritten.

    :returns: A `CommCareCase` instance.
    """
    from corehq.form_processor.models import CommCareCase

    data = hit.get("_source", hit)
    _VALUE = VALUE
    case = CommCareCase(
        case_id=data.get("_id", None),
        case_json={
            prop["key"]: prop[_VALUE]
            for prop in data.get(CASE_PROPERTIES_PATH, {})
            if prop["key"] not in INDEXED_METADATA_BY_KEY
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
