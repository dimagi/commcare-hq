from __future__ import absolute_import
from __future__ import unicode_literals
from functools import wraps

from django.http import HttpResponseRedirect

from .utils import get_dropbox_auth_flow
from .views import DROPBOX_ACCESS_TOKEN


def require_dropbox_session(next_url=None):
    """
    Any view that is wrapped with this will redirect to the dropbox authorization site if the user does not
    have an access_token in their session.

    @params
    next_url - The next_url to go to after redirect. Can be a function or string. If it's a function it will
    receive the same parameters as the view
    """
    def decorator(view_func):
        @wraps(view_func)
        def inner(request, *args, **kwargs):
            if not request.session.get(DROPBOX_ACCESS_TOKEN, None):
                url = '/'
                if hasattr(next_url, '__call__'):
                    url = next_url(request, *args, **kwargs)
                elif next_url:
                    url = next_url
                request.session['dropbox_next_url'] = url
                authorize_url = get_dropbox_auth_flow(request.session).start()
                return HttpResponseRedirect(authorize_url)
            return view_func(request, *args, **kwargs)
        return inner
    return decorator
