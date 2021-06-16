from functools import wraps

from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.urls.base import reverse

from corehq.apps.linked_domain.dbaccessors import get_domain_master_link

REMOTE_REQUESTER_HEADER = 'HTTP_HQ_REMOTE_REQUESTER'


def require_linked_domain(fn):
    @wraps(fn)
    def _inner(request, domain, *args, **kwargs):
        requester = request.META.get(REMOTE_REQUESTER_HEADER, None)
        if not requester:
            return HttpResponseBadRequest()

        # Check if this is a linked domain "pulling" content from a master domain
        link = get_domain_master_link(requester)
        if link and link.master_domain == domain:
            return fn(request, domain, *args, **kwargs)

        # Check if this is a master domain "pushing" content to a linked domain
        link = get_domain_master_link(domain)
        if link:
            expected_requester = link.remote_base_url + reverse("domain_homepage", args=[link.master_domain])
            if requester == expected_requester:
                return fn(request, domain, *args, **kwargs)

        return HttpResponseForbidden()

    return _inner
