from __future__ import absolute_import
from django.http import Http404


def require_uth_domain(view_func):
    def shim(request, domain, *args, **kwargs):
        if domain == 'uth-rhd':
            return view_func(request, domain, *args, **kwargs)
        else:
            raise Http404()
    return shim
