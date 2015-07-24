from functools import wraps

from django.http import HttpResponseRedirect

from .utils import get_dropbox_auth_flow
from .views import DROPBOX_ACCESS_TOKEN


def require_dropbox_session(next_url=None):
    def decorator(view_func):
        @wraps(view_func)
        def inner(request, *args, **kwargs):
            if not request.session.get(DROPBOX_ACCESS_TOKEN, None):
                url = '/'
                if hasattr(next_url, '__call__'):
                    next_url(request, *args, **kwargs)
                elif next_url:
                    url = next_url
                request.session['dropbox_next_url'] = url
                authorize_url = get_dropbox_auth_flow(request.session).start()
                return HttpResponseRedirect(authorize_url)

            return view_func(request, *args, **kwargs)
        return inner
    return decorator
