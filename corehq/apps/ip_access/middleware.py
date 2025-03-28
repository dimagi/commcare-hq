from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext_lazy as _

from dimagi.utils.web import get_ip

from corehq.toggles import IP_ACCESS_CONTROLS

from .models import IPAccessConfig

MSG = _("You cannot access this page from your current IP address")


class IPAccessMiddleware(MiddlewareMixin):

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated or 'domain' not in view_kwargs:
            return

        domain = view_kwargs['domain']
        if IP_ACCESS_CONTROLS.enabled(domain) and not is_valid_ip(request, domain):
            return HttpResponse(MSG, status=451)


def is_valid_ip(request, domain):
    ip = get_ip(request)
    key = f"hq_session_ips-{domain}"
    if key not in request.session:
        request.session[key] = []
    if ip in request.session[key]:
        return True
    else:
        try:
            config = IPAccessConfig.objects.get(domain=domain)
        except IPAccessConfig.DoesNotExist:
            config = None
        if not config or config.is_allowed(ip):
            request.session[key].append(ip)
            return True
        return False
