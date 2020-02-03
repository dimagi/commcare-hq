from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.cloudcare.models import ApplicationAccess
from corehq.util.quickcache import quickcache


@quickcache(['domain'])
def get_application_access_for_domain(domain):
    """
    There should only be one of these per domain,
     return it if found, otherwise create it.
    """
    return ApplicationAccess.objects.get_or_create(domain=domain)[0]


def get_cloudcare_apps(domain):
    apps = get_brief_apps_in_domain(domain, include_remote=False)
    return [app for app in apps if app.cloudcare_enabled]
