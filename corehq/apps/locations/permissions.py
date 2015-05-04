from django_prbac.decorators import requires_privilege_raise404
from corehq import privileges
from corehq.apps.domain.decorators import (login_and_domain_required,
                                           domain_admin_required)


def locations_access_required(view_fn):
    """
    Decorator controlling domain-level access to locations.
    """
    return login_and_domain_required(
        requires_privilege_raise404(privileges.LOCATIONS)(view_fn)
    )


def is_locations_admin(view_fn):
    """
    Decorator controlling write access to locations.
    """
    return locations_access_required(domain_admin_required(view_fn))
