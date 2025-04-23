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
        if IP_ACCESS_CONTROLS.enabled(domain) and not is_valid_ip(request, domain):
            raise IPPermissionDenied()


def is_valid_ip(request, domain):
    ip = get_ip(request)
    block_key = f"hq_session_blocked_ips-{domain}"
    allow_key = f"hq_session_ips-{domain}"
    if block_key not in request.session:
        request.session[block_key] = []
    if allow_key not in request.session:
        request.session[allow_key] = []

    if ip in request.session[block_key]:
        return False
    if ip in request.session[allow_key]:
        return True

    try:
        config = IPAccessConfig.objects.get(domain=domain)
    except IPAccessConfig.DoesNotExist:
        config = None
    if not config or config.is_allowed(ip):
        request.session[allow_key].append(ip)
        return True
    else:
        request.session[block_key].append(ip)
        return False
