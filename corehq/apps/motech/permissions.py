from corehq.apps.domain.decorators import domain_admin_required
from corehq.toggles import MOTECH

require_motech_permissions = lambda fn: MOTECH.required_decorator()(domain_admin_required(fn))
