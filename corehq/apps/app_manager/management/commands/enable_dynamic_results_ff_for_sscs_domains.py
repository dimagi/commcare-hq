from django.core.management import BaseCommand

from corehq.apps.case_search.models import CaseSearchConfig
from corehq.toggles import DYNAMICALLY_UPDATE_SEARCH_RESULTS, NAMESPACE_DOMAIN


class Command(BaseCommand):
    help = """
    Enable DYNAMICALLY_UPDATE_SEARCH_RESULTS feature flag for domains
    with CaseSearchConfig.split_screen_ui enabled.

    This command ignores domain subscription, so it includes domains
    that aren't yet, or are no longer, on Advanced or Enterprise plans.
    Domains will only see the split screen case search UI and
    dynamically updated search results when they are on Advanced or
    Enterprise plans.
    """

    def handle(self, **options):
        domains = get_split_screen_ui_enabled_domains()
        print(f"Processing {len(domains)} domains")
        for domain in domains:
            DYNAMICALLY_UPDATE_SEARCH_RESULTS.set(domain, True, NAMESPACE_DOMAIN)


def get_split_screen_ui_enabled_domains():
    configs = CaseSearchConfig.objects.filter(split_screen_ui=True)
    return [conf.domain for conf in configs]
