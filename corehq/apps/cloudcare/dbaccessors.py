from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.cloudcare.models import ApplicationAccess


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
    return [
        app for app in ApplicationBase.get_db().view(
            'app_manager/applications_brief', startkey=[domain], endkey=[domain, {}])
        if app['doc_type'] == 'Application' and app['cloudcare_enabled']
    ]
