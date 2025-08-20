from django.conf import settings
from memoized import memoized

from . import (  # noqa: F401
    # "utility" modules
    aggregations,
    client,
    const,
    es_query,
    exceptions,
    index,
    filters,
    migration_operations,
    queries,
    utils,
    # "model" modules
    apps,
    case_search,
    case_search_sub,
    cases,
    domains,
    forms,
    groups,
    users,
    sms,
)
from .es_query import ESQuery, HQESQuery  # noqa: F401

AppES = apps.AppES
CaseES = cases.CaseES
DomainES = domains.DomainES
FormES = forms.FormES
GroupES = groups.GroupES
UserES = users.UserES
CaseSearchES = case_search.CaseSearchES
CaseSearchBhaES = case_search_sub.CaseSearchBhaES
CaseSearchCCPerfES = case_search_sub.CaseSearchCCPerfES

app_adapter = apps.app_adapter
case_adapter = cases.case_adapter
case_search_adapter = case_search.case_search_adapter
domain_adapter = domains.domain_adapter
form_adapter = forms.form_adapter
group_adapter = groups.group_adapter
sms_adapter = sms.sms_adapter
user_adapter = users.user_adapter
case_search_bha_adapter = case_search_sub.case_search_bha_adapter
case_search_cc_perf_adapter = case_search_sub.case_search_cc_perf_adapter


@memoized
def canonical_name_adapter_map():
    """
    Due to custom indices created in SaaS environments, we need this to by dynamic.
    """
    adapter_map = {
        app_adapter.canonical_name: app_adapter,
        case_adapter.canonical_name: case_adapter,
        case_search_adapter.canonical_name: case_search_adapter,
        domain_adapter.canonical_name: domain_adapter,
        form_adapter.canonical_name: form_adapter,
        group_adapter.canonical_name: group_adapter,
        sms_adapter.canonical_name: sms_adapter,
        user_adapter.canonical_name: user_adapter,
    }
    if settings.ENABLE_BHA_CASE_SEARCH_ADAPTER:
        adapter_map[case_search_bha_adapter.canonical_name] = case_search_bha_adapter
        adapter_map[case_search_cc_perf_adapter.canonical_name] = case_search_cc_perf_adapter
    return adapter_map
