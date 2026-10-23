from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain
from corehq.apps.domain.utils import is_domain_active


def public_webforms_enabled(domain):
    return (
        is_domain_active(domain)
        and domain_has_privilege(domain, privileges.PUBLIC_WEBFORMS)
        and toggles.PUBLIC_WEBFORMS.enabled(domain, namespace=toggles.NAMESPACE_DOMAIN)
    )


def is_app_live(domain, app_id):
    return app_id in get_live_app_ids(domain)


def get_live_app_ids(domain):
    return set(get_app_ids_in_domain(domain))
