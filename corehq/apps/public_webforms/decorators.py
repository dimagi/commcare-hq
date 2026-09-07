from functools import wraps

from corehq.apps.public_webforms.models import (
    PublicFormSession,
    PublicFormUser,
)

PUBLIC_FORM_SESSION_COOKIE_NAME = 'public_form_session_key'
PUBLIC_FORM_SESSION_HEADER = 'CommCare-Public-Session'


def allow_public_form_session(view_func):
    """
    Adds public form session auth as an accepted auth mode for a view.

    When the request carries the public form session header and a cookie
    whose key resolves to a valid, usable PublicFormSession, sets
    ``request.couch_user`` to a PublicFormUser proxy for that session.
    """

    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        session = _get_public_form_session(request)
        if session is not None:
            request.couch_user = PublicFormUser(session)
        return view_func(request, *args, **kwargs)

    return _inner


def _get_public_form_session(request):
    if request.headers.get(PUBLIC_FORM_SESSION_HEADER) != 'true':
        return None
    raw_key = request.COOKIES.get(PUBLIC_FORM_SESSION_COOKIE_NAME)
    if not raw_key:
        return None
    return PublicFormSession.get_active_session_by_key(raw_key)
