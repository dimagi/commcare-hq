from collections import namedtuple

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

# Properties added to the case search mapping to provide extra information
SYSTEM_PROPERTIES = [
    CASE_PROPERTIES_PATH,
    INDEXED_ON,
]


def get_field_lambda(field_name):
    return lambda model: model._meta.get_field(field_name)


# Properties that are inconsistent between case models stored in HQ and casedb
# expressions. We store these as case properties in the case search index so
# they are easily searchable, then remove them when pulling the case source
# from ES
SpecialCaseProperty = namedtuple('SpecialCaseProperty', 'key value_getter sort_property field_getter')
SPECIAL_CASE_PROPERTIES_MAP = {
    '@case_id': SpecialCaseProperty('@case_id', lambda doc: doc.get('_id'), '_id',
                                    get_field_lambda('case_id')),
    '@case_type': SpecialCaseProperty('@case_type', lambda doc: doc.get('type'), 'type.exact',
                                      get_field_lambda('type')),

    '@owner_id': SpecialCaseProperty('@owner_id', lambda doc: doc.get('owner_id'), 'owner_id',
                                     get_field_lambda('owner_id')),

    '@status': SpecialCaseProperty('@status', lambda doc: 'closed' if doc.get('closed') else 'open', 'closed',
                                   get_field_lambda('closed')),

    'name': SpecialCaseProperty('name', lambda doc: doc.get('name'), 'name.exact',
                                get_field_lambda('name')),
    'case_name': SpecialCaseProperty('case_name', lambda doc: doc.get('name'), 'name.exact',
                                     get_field_lambda('name')),

    'external_id': SpecialCaseProperty('external_id', lambda doc: doc.get('external_id', ''), 'external_id',
                                       get_field_lambda('external_id')),
    'date_opened': SpecialCaseProperty('date_opened', lambda doc: doc.get('opened_on'), 'opened_on',
                                       get_field_lambda('opened_on')),
    'closed_on': SpecialCaseProperty('closed_on', lambda doc: doc.get('closed_on'), 'closed_on',
                                     get_field_lambda('closed_on')),
    'last_modified': SpecialCaseProperty('last_modified', lambda doc: doc.get('modified_on'), 'modified_on',
                                         get_field_lambda('modified_on')),
}

SPECIAL_CASE_PROPERTIES = list(SPECIAL_CASE_PROPERTIES_MAP.keys())


# Properties that can be shown in the report but are not stored on the case or in the case index
# These properties are computed in `SafeCaseDisplay` when each case is displayed
# Hence, they cannot be sorted on
CASE_COMPUTED_METADATA = [
    'closed_by_username',
    'last_modified_by_user_username',
    'opened_by_username',
    'owner_name',
    'closed_by_user_id',
    'opened_by_user_id',
    'server_last_modified_date',
]

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
