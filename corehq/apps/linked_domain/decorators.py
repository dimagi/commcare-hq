from functools import wraps

from django.http import Http404, HttpResponseForbidden

from corehq.apps.linked_domain.util import can_user_access_linked_domains


def require_access_to_linked_domains(view_func):
    @wraps(view_func)
    def _inner(request, domain, *args, **kwargs):
        if not hasattr(request, 'couch_user'):
            raise Http404()

        couch_user = request.couch_user

        def call_view():
            return view_func(request, domain, *args, **kwargs)
        if can_user_access_linked_domains(couch_user, domain):
            return call_view()
        else:
            return HttpResponseForbidden()

    return _inner
