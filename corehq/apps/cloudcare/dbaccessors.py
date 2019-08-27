from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.cloudcare.models import ApplicationAccess
from corehq.util.quickcache import quickcache


@quickcache(['domain'])
def get_application_access_for_domain(domain):
    """
    there should only be one ApplicationAccess per domain,
    return it if found, otherwise None.

    if more than one is found, one is arbitrarily returned.
    """
    return ApplicationAccess.view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'ApplicationAccess'],
        endkey=[domain, 'ApplicationAccess', {}],
        include_docs=True,
        reduce=False,
    ).first()


def get_cloudcare_apps(domain):
    apps = get_brief_apps_in_domain(domain, include_remote=False)
    return [app for app in apps if app.cloudcare_enabled]
