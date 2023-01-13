from django.core.management import BaseCommand

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import domain_has_apps, get_app_ids_in_domain, get_current_app
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "One-time command to enable search filter flag where 'search filter' is already in use"

    def handle(self, **options):
        flag_domains_using_search_filter()


def flag_domains_using_search_filter():
    domains = (
        set(toggles.USH_CASE_CLAIM_UPDATES.get_enabled_domains())
        - set(toggles.USH_SEARCH_FILTER.get_enabled_domains())
    )
    for domain in with_progress_bar(domains):
        enabled = domain_has_apps(domain) and _any_app_uses_search_filter(domain)
        toggles.USH_SEARCH_FILTER.set(domain, enabled, namespace=toggles.NAMESPACE_DOMAIN)


def _any_app_uses_search_filter(domain):
    for app_id in get_app_ids_in_domain(domain):
        app = get_current_app(domain, app_id)
        if app.has_modules() and _any_module_uses_search_filter(app):
            return True
    return False


def _any_module_uses_search_filter(app):
    for module in app.modules:
        if module.search_config.search_filter:
            return True
    return False
