from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext_lazy as _

from dimagi.utils.web import get_ip

from corehq.toggles import IP_ACCESS_CONTROLS

from .models import IPAccessConfig


class IPPermissionDenied(PermissionDenied):
    user_facing_message = _(
        "You cannot access this page from your current IP address"
    )


class IPAccessMiddleware(MiddlewareMixin):

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated or 'domain' not in view_kwargs:
            return

        domain = view_kwargs['domain']
        if (
            IP_ACCESS_CONTROLS.enabled(domain)
            and not is_valid_ip(request.session, get_ip(request), domain)
        ):
            raise IPPermissionDenied()


def is_valid_ip(session, ip, domain):
    """
    Whether ``ip`` may access ``domain``, remembering the answer in
    ``session`` so each IP is looked up at most once per session.
    """
    block_key = f"hq_session_blocked_ips-{domain}"
    allow_key = f"hq_session_ips-{domain}"
    if block_key not in session:
        session[block_key] = []
    if allow_key not in session:
        session[allow_key] = []

    if ip in session[block_key]:
        return False
    if ip in session[allow_key]:
        return True

    try:
        config = IPAccessConfig.objects.get(domain=domain)
    except IPAccessConfig.DoesNotExist:
        config = None
    if not config or config.is_allowed(ip):
        session[allow_key].append(ip)
        return True
    else:
        session[block_key].append(ip)
        return False
