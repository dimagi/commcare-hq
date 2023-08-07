from django.conf import settings


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


HQ_APPS_INDEX_CANONICAL_NAME = "apps"
HQ_APPS_INDEX_NAME = "hqapps_2020-02-26"
HQ_APPS_SECONDARY_INDEX_NAME = "apps-20230524"

HQ_CASE_SEARCH_INDEX_CANONICAL_NAME = "case_search"
HQ_CASE_SEARCH_INDEX_NAME = getattr(settings, "ES_CASE_SEARCH_INDEX_NAME", "case_search_2018-05-29")
HQ_CASE_SEARCH_SECONDARY_INDEX_NAME = "case-search-20230524"

HQ_CASES_INDEX_CANONICAL_NAME = "cases"
HQ_CASES_INDEX_NAME = "hqcases_2016-03-04"
HQ_CASES_SECONDARY_INDEX_NAME = "cases-20230524"

HQ_DOMAINS_INDEX_CANONICAL_NAME = "domains"
HQ_DOMAINS_INDEX_NAME = "hqdomains_2021-03-08"
HQ_DOMAINS_SECONDARY_INDEX_NAME = "domains-20230524"

HQ_FORMS_INDEX_CANONICAL_NAME = "forms"
HQ_FORMS_INDEX_NAME = getattr(settings, "ES_XFORM_INDEX_NAME", "xforms_2016-07-07")
HQ_FORMS_SECONDARY_INDEX_NAME = "forms-20230524"

HQ_GROUPS_INDEX_CANONICAL_NAME = "groups"
HQ_GROUPS_INDEX_NAME = "hqgroups_2017-05-29"
HQ_GROUPS_SECONDARY_INDEX_NAME = "groups-20230524"

HQ_SMS_INDEX_CANONICAL_NAME = "sms"
HQ_SMS_INDEX_NAME = "smslogs_2020-01-28"
HQ_SMS_SECONDARY_INDEX_NAME = "sms-20230524"

HQ_USERS_INDEX_CANONICAL_NAME = "users"
HQ_USERS_INDEX_NAME = "hqusers_2017-09-07"
HQ_USERS_SECONDARY_INDEX_NAME = "users-20230524"
