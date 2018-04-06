from __future__ import absolute_import
from __future__ import unicode_literals
from importlib import import_module

from django.conf import settings
from django.contrib.auth import get_user

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.models import CouchUser


def login_with_permission_from_post(login_decorator=login_and_domain_required):
    """
        This sets user and couch_user in the request from a cookie passed in the POST variables.
        This gets around a limitation in flash (known manifistation in Firefox) where you can't
        insert the cookie directly into the header of the request.
    """
    def view_decorator(view_func):
        def new_view(req, domain, *args, **kwargs):
            if req.method == 'POST':
                cookie = req.POST.get('_cookie')
                if cookie:
                    cookies = dict([x.strip().split('=', 1) for x in cookie.split(';')])

                    session_key = cookies.get(settings.SESSION_COOKIE_NAME, None)
                    engine = import_module(settings.SESSION_ENGINE)
                    req.session = engine.SessionStore(session_key)

                    req.user = get_user(req)
                    req.couch_user = CouchUser.from_django_user(req.user)
            return login_decorator(view_func)(req, domain, *args, **kwargs)
        return new_view
    return view_decorator
