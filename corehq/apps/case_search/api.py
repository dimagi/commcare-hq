from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.case_search.tasks import reindex_case_search_for_domain, delete_case_search_cases_for_domain


def enable_case_search(domain):
    config, created = CaseSearchConfig.objects.get_or_create(pk=domain)
    if not config.enabled:
        config.enabled = True
        config.save()
        reindex_case_search_for_domain.delay(domain)


def disable_case_search(domain):
    try:
        config = CaseSearchConfig.objects.get(pk=domain)
    except CaseSearchConfig.DoesNotExist:
        # CaseSearch was never enabled
        return
    if config.enabled:
        config.enabled = False
        config.save()
        delete_case_search_cases_for_domain.delay(domain)
