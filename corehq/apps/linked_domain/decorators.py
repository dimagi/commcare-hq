from functools import wraps

from django.http import HttpResponseBadRequest, HttpResponseForbidden

from corehq.apps.linked_domain.dbaccessors import get_domain_master_link


def require_linked_domain(fn):
    @wraps(fn)
    def _inner(request, domain, *args, **kwargs):
        requester = request.META.get('HTTP_HQ_REMOTE_REQUESTER', None)
        if not requester:
            return HttpResponseBadRequest()

        link = get_domain_master_link(requester)
        if not link or link.master_domain != domain:
            return HttpResponseForbidden()

        return fn(request, domain, *args, **kwargs)

    return _inner
