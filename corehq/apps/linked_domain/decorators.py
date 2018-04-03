from __future__ import absolute_import
from __future__ import unicode_literals
from functools import wraps

from django.http import HttpResponseBadRequest, HttpResponseForbidden

from corehq.apps.linked_domain.dbaccessors import get_domain_master_link

REMOTE_REQUESTER_HEADER = 'HTTP_HQ_REMOTE_REQUESTER'


def require_linked_domain(fn):
    @wraps(fn)
    def _inner(request, domain, *args, **kwargs):
        requester = request.META.get(REMOTE_REQUESTER_HEADER, None)
        if not requester:
            return HttpResponseBadRequest()

        link = get_domain_master_link(requester)
        if not link or link.master_domain != domain:
            return HttpResponseForbidden()

        return fn(request, domain, *args, **kwargs)

    return _inner
