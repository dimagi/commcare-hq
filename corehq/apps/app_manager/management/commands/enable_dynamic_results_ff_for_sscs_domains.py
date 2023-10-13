from django.core.management import BaseCommand
from corehq.toggles import SPLIT_SCREEN_CASE_SEARCH, DYNAMICALLY_UPDATE_SEARCH_RESULTS, NAMESPACE_DOMAIN


class Command(BaseCommand):
    help = """
    Enabled DYNAMICALLY_UPDATE_SEARCH_RESULTS feature flag for domains with SPLIT_SCREEN_CASE_SEARCH enabled.
    """

    def handle(self, **options):
        sscs_enabled_domains = SPLIT_SCREEN_CASE_SEARCH.get_enabled_domains()
        print("Processing " + str(len(sscs_enabled_domains)) + " domains")
        for domain in sscs_enabled_domains:
            DYNAMICALLY_UPDATE_SEARCH_RESULTS.set(domain, True, NAMESPACE_DOMAIN)
