from dataclasses import dataclass
from typing import Callable

from corehq.apps.es import filters

# Case properties nested documents
CASE_PROPERTIES_PATH = 'case_properties'
VALUE = 'value'
GEOPOINT_VALUE = 'geopoint_value'

# Case indices nested documents
INDICES_PATH = 'indices'
REFERENCED_ID = 'referenced_id'
IDENTIFIER = 'identifier'

# Maximum number of results to pull from ElasticSearch
CASE_SEARCH_MAX_RESULTS = 500

# Added to each case response when case searches are performed
RELEVANCE_SCORE = "commcare_search_score"
COMMCARE_PROJECT = "commcare_project"
# Added to secondary results in case search to filter them out of the case list
IS_RELATED_CASE = "commcare_is_related_case"
EXCLUDE_RELATED_CASES_FILTER = "[not(commcare_is_related_case=true())]"

# Added to each case on the index for debugging when a case was added to ES
INDEXED_ON = '@indexed_on'


@dataclass(frozen=True)
class _INDEXED_METADATA:
    key: str  # The user-facing property name
    system_name: str  # The CommCareCase field name
    is_datetime: bool = False
    _es_field_name: str = None  # Path to use for ES logic, if not system_name
    _value_getter: Callable = None

    def get_value(self, doc):
        if self._value_getter:
            return self._value_getter(doc)
        return doc.get(self.system_name)

    @property
    def es_field_name(self):
        return self._es_field_name or self.system_name


# These are top level, schema'd properties on CommCareCase that are made
# available to the user in interactions with the case search Elasticsearch
# index.
# These are stored along with dynamic case properties in the case search index
# to be easily searchable, then removed when pulling the case source from ES.
INDEXED_METADATA_BY_KEY = {prop.key: prop for prop in [
    _INDEXED_METADATA(
        key='@case_id',
        system_name='_id',
    ),
    _INDEXED_METADATA(
        key='@case_type',
        system_name='type',
        _es_field_name='type.exact',
    ),
    _INDEXED_METADATA(
        key='@owner_id',
        system_name='owner_id',
    ),
    _INDEXED_METADATA(
        key='@status',
        system_name='closed',
        _value_getter=lambda doc: 'closed' if doc.get('closed') else 'open',
    ),
    _INDEXED_METADATA(
        key='name',
        system_name='name',
        _es_field_name='name.exact',
    ),
    _INDEXED_METADATA(
        key='case_name',
        system_name='name',
        _es_field_name='name.exact',
    ),
    _INDEXED_METADATA(
        key='external_id',
        system_name='external_id',
        _value_getter=lambda doc: doc.get('external_id', ''),
    ),
    _INDEXED_METADATA(
        key='date_opened',
        system_name='opened_on',
        is_datetime=True,
    ),
    _INDEXED_METADATA(
        key='closed_on',
        system_name='closed_on',
        is_datetime=True,
    ),
    _INDEXED_METADATA(
        key='last_modified',
        system_name='modified_on',
        is_datetime=True,
    ),
]}

# Properties that can be shown in the report but are not stored on the case or in the case index
# These properties are computed in `SafeCaseDisplay` when each case is displayed
# Hence, they cannot be sorted on
COMPUTED_METADATA = [
    'closed_by_username',
    'last_modified_by_user_username',
    'opened_by_username',
    'owner_name',
    'closed_by_user_id',
    'opened_by_user_id',
    'server_last_modified_date',
]
METADATA_IN_REPORTS = list(INDEXED_METADATA_BY_KEY) + COMPUTED_METADATA

MAX_RELATED_CASES = 500000  # Limit each related case lookup to return 500,000 cases to prevent timeouts
OPERATOR_MAPPING = {
    'and': filters.AND,
    'or': filters.OR,
}
RANGE_OP_MAPPING = {
    '>': 'gt',
    '>=': 'gte',
    '<': 'lt',
    '<=': 'lte',
}
EQ = "="
NEQ = "!="
COMPARISON_OPERATORS = [EQ, NEQ] + list(RANGE_OP_MAPPING.keys())
ALL_OPERATORS = COMPARISON_OPERATORS + list(OPERATOR_MAPPING.keys())

DOCS_LINK_CASE_LIST_EXPLORER = "https://confluence.dimagi.com/display/commcarepublic/Case+List+Explorer"
