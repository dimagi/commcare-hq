from corehq.apps.es.utils import get_es_reindex_setting_value

SIZE_LIMIT = 1000000

# this is what ES's maxClauseCount is currently set to, can change this config
# value if we want to support querying over more domains
MAX_CLAUSE_COUNT = 1024

# Default scroll parameters (same values hard-coded in elasticsearch-py's
# `scan()` helper).
SCROLL_KEEPALIVE = '5m'
SCROLL_SIZE = 1000

# index settings
INDEX_CONF_REINDEX = {
    "index.refresh_interval": "1800s",
    "index.max_result_window": SIZE_LIMIT,
}

INDEX_CONF_STANDARD = {
    "index.refresh_interval": "5s",
    "index.max_result_window": SIZE_LIMIT,
}

INDEX_SLOWLOG_CONF = {
    "index.search.slowlog.threshold.query.warn": "10s",
    "index.search.slowlog.threshold.query.info": "5s",
    "index.search.slowlog.threshold.query.debug": "2s",
    "index.search.slowlog.threshold.query.trace": "500ms",
}

HQ_APPS_INDEX_CANONICAL_NAME = "apps"
HQ_APPS_INDEX_NAME = "apps-2024-05-09"
HQ_APPS_SECONDARY_INDEX_NAME = None

HQ_CASE_SEARCH_INDEX_CANONICAL_NAME = "case_search"
HQ_CASE_SEARCH_INDEX_NAME = "case-search-2024-05-09"
HQ_CASE_SEARCH_SECONDARY_INDEX_NAME = None

# See case_search_sub.py docstring for context
HQ_CASE_SEARCH_BHA_INDEX_CANONICAL_NAME = "case_search_bha"
HQ_CASE_SEARCH_BHA_INDEX_NAME = "case-search-bha-2024-05-10"
HQ_CASE_SEARCH_BHA_SECONDARY_INDEX_NAME = None

HQ_CASE_SEARCH_CC_PERF_INDEX_CANONICAL_NAME = "case_search_cc_perf"
HQ_CASE_SEARCH_CC_PERF_INDEX_NAME = "case-search-cc-perf-2025-06-19"
HQ_CASE_SEARCH_CC_PERF_SECONDARY_INDEX_NAME = None

HQ_CASES_INDEX_CANONICAL_NAME = "cases"
HQ_CASES_INDEX_NAME = "cases-2024-05-09"
HQ_CASES_SECONDARY_INDEX_NAME = None

HQ_DOMAINS_INDEX_CANONICAL_NAME = "domains"
HQ_DOMAINS_INDEX_NAME = "domains-2024-05-09"
HQ_DOMAINS_SECONDARY_INDEX_NAME = None

HQ_FORMS_INDEX_CANONICAL_NAME = "forms"
HQ_FORMS_INDEX_NAME = "forms-2024-05-09"
HQ_FORMS_SECONDARY_INDEX_NAME = None

HQ_GROUPS_INDEX_CANONICAL_NAME = "groups"
HQ_GROUPS_INDEX_NAME = "groups-2024-05-09"
HQ_GROUPS_SECONDARY_INDEX_NAME = None

HQ_SMS_INDEX_CANONICAL_NAME = "sms"
HQ_SMS_INDEX_NAME = "sms-2024-05-09"
HQ_SMS_SECONDARY_INDEX_NAME = None

HQ_USERS_INDEX_CANONICAL_NAME = "users"
HQ_USERS_INDEX_NAME = "users-2024-05-09"
HQ_USERS_SECONDARY_INDEX_NAME = None

ES_REINDEX_LOG = [
    '6',
    '7'
]


ES_APPS_INDEX_MULTIPLEXED = get_es_reindex_setting_value('ES_APPS_INDEX_MULTIPLEXED', False)
ES_CASE_SEARCH_INDEX_MULTIPLEXED = get_es_reindex_setting_value('ES_CASE_SEARCH_INDEX_MULTIPLEXED', False)
ES_CASES_INDEX_MULTIPLEXED = get_es_reindex_setting_value('ES_CASES_INDEX_MULTIPLEXED', False)
ES_DOMAINS_INDEX_MULTIPLEXED = get_es_reindex_setting_value('ES_DOMAINS_INDEX_MULTIPLEXED', False)
ES_FORMS_INDEX_MULTIPLEXED = get_es_reindex_setting_value('ES_FORMS_INDEX_MULTIPLEXED', False)
ES_GROUPS_INDEX_MULTIPLEXED = get_es_reindex_setting_value('ES_GROUPS_INDEX_MULTIPLEXED', False)
ES_SMS_INDEX_MULTIPLEXED = get_es_reindex_setting_value('ES_SMS_INDEX_MULTIPLEXED', False)
ES_USERS_INDEX_MULTIPLEXED = get_es_reindex_setting_value('ES_USERS_INDEX_MULTIPLEXED', False)


ES_APPS_INDEX_SWAPPED = get_es_reindex_setting_value('ES_APPS_INDEX_SWAPPED', False)
ES_CASE_SEARCH_INDEX_SWAPPED = get_es_reindex_setting_value('ES_CASE_SEARCH_INDEX_SWAPPED', False)
ES_CASES_INDEX_SWAPPED = get_es_reindex_setting_value('ES_CASES_INDEX_SWAPPED', False)
ES_DOMAINS_INDEX_SWAPPED = get_es_reindex_setting_value('ES_DOMAINS_INDEX_SWAPPED', False)
ES_FORMS_INDEX_SWAPPED = get_es_reindex_setting_value('ES_FORMS_INDEX_SWAPPED', False)
ES_GROUPS_INDEX_SWAPPED = get_es_reindex_setting_value('ES_GROUPS_INDEX_SWAPPED', False)
ES_SMS_INDEX_SWAPPED = get_es_reindex_setting_value('ES_SMS_INDEX_SWAPPED', False)
ES_USERS_INDEX_SWAPPED = get_es_reindex_setting_value('ES_USERS_INDEX_SWAPPED', False)


ES_FOR_TEST_INDEX_MULTIPLEXED = get_es_reindex_setting_value('ES_FOR_TEST_INDEX_MULTIPLEXED', False)
ES_FOR_TEST_INDEX_SWAPPED = get_es_reindex_setting_value('ES_FOR_TEST_INDEX_MULTIPLEXED', False)
