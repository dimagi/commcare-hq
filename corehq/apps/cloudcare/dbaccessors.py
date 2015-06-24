from corehq.apps.cloudcare.models import ApplicationAccess


def get_application_access_for_domain(domain):
    """
    there should only be one ApplicationAccess per domain,
    return it if found, otherwise None.

    if more than one is found, one is arbitrarily returned.
    """
    return ApplicationAccess.view(
        'cloudcare/application_access',
        key=domain,
        include_docs=True
    ).first()
