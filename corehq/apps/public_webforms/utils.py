from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.utils import is_domain_active


def public_webforms_enabled(domain):
    return (
        is_domain_active(domain)
        and domain_has_privilege(domain, privileges.PUBLIC_WEBFORMS)
        and toggles.PUBLIC_WEBFORMS.enabled(domain, namespace=toggles.NAMESPACE_DOMAIN)
    )
