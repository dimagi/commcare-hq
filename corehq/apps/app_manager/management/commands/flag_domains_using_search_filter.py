from datetime import datetime
import traceback

from django.core.management import BaseCommand

from dimagi.utils.chunked import chunked
from corehq import toggles
from corehq.apps.app_manager.dbaccessors import domain_has_apps, get_app_ids_in_domain, get_current_app
from corehq.util.log import with_progress_bar

APP_WRAPPING_ERRORS_LOG = "migrate_to_search_filter_flag_wrapping_errors.txt"


class Command(BaseCommand):
    help = "One-time command to enable search filter flag where 'search filter' is already in use"

    def handle(self, **options):
        flag_domains_using_search_filter()


def flag_domains_using_search_filter():
    domains = toggles.USH_CASE_CLAIM_UPDATES.get_enabled_domains()
    for chunk in chunked(with_progress_bar(domains), 100):
        for domain in chunk:
            enabled = domain_has_apps(domain) and _any_app_uses_search_filter(domain)
            toggles.USH_SEARCH_FILTER.set(domain, enabled, namespace=toggles.NAMESPACE_DOMAIN)


def _any_app_uses_search_filter(domain):
    for app_id in get_app_ids_in_domain(domain):
        try:
            app = get_current_app(domain, app_id)
        except Exception:
            log_error(domain, app_id)
        else:
            if app.modules and _any_module_uses_search_filter(app):
                return True
    return False


def _any_module_uses_search_filter(app):
    for module in app.modules:
        if hasattr(module, 'search_config') and module.search_config.search_filter:
            return True
    return False


def log_error(domain, app_id):
    with open(APP_WRAPPING_ERRORS_LOG, 'a') as f:
        error_string = (f"{datetime.now()}\nOn domain: {domain}, "
                        f"App ID: {app_id}\n{traceback.format_exc().strip()}\n")
        f.write(error_string)
