import attr

# Case properties nested documents
CASE_PROPERTIES_PATH = 'case_properties'
VALUE = 'value'

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


@attr.s
class SpecialCaseProperty:

    def _doc_key(self):
        return self.doc_key

    def _getter(self):
        doc_key, default = self.doc_key, self.default
        return lambda doc: doc.get(doc_key, default)

    key = attr.ib()
    doc_key = attr.ib()
    sort_property = attr.ib(default=attr.Factory(_doc_key, takes_self=True))
    case_property = attr.ib(default=attr.Factory(_doc_key, takes_self=True))
    default = attr.ib(default=None)
    value_getter = attr.ib(default=attr.Factory(_getter, takes_self=True))


# Properties that are inconsistent between case models stored in HQ and casedb
# expressions. We store these as case properties in the case search index so
# they are easily searchable, then remove them when pulling the case source
# from ES
SPECIAL_CASE_PROPERTIES_MAP = {prop.key: prop for prop in [
    SpecialCaseProperty('@case_id', '_id', case_property="case_id"),
    SpecialCaseProperty('@case_type', 'type', 'type.exact'),

    SpecialCaseProperty('@owner_id', 'owner_id'),

    SpecialCaseProperty('@status', 'closed',
        value_getter=lambda doc: 'closed' if doc.get('closed') else 'open'),

    SpecialCaseProperty('name', 'name', 'name.exact'),
    SpecialCaseProperty('case_name', 'name', 'name.exact'),

    SpecialCaseProperty('external_id', 'external_id', default=''),

    SpecialCaseProperty('date_opened', 'opened_on'),
    SpecialCaseProperty('closed_on', 'closed_on'),
    SpecialCaseProperty('last_modified', 'modified_on'),
]}
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
