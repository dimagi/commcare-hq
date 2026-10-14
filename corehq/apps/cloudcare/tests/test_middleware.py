from types import SimpleNamespace
from uuid import uuid4

from django.http import HttpResponse
from django.test import RequestFactory

from corehq.apps.cloudcare.middleware import (
    FORMPLAYER_SESSION_COOKIE_NAME,
    CloudcareMiddleware,
)
from corehq.apps.users.util import PUBLIC_USER_ID


def _process_response(cookies=None, couch_user=None, public_form_session=None):
    request = RequestFactory().get('/')
    request.COOKIES = dict(cookies or {})
    if couch_user is not None:
        request.couch_user = couch_user
    if public_form_session is not None:
        request.public_form_session = public_form_session
    middleware = CloudcareMiddleware(lambda request: HttpResponse())
    return middleware.process_response(request, HttpResponse())


def test_routes_a_signed_in_user_on_their_user_id():
    response = _process_response(couch_user=SimpleNamespace(user_id='abc123'))

    assert response.cookies[FORMPLAYER_SESSION_COOKIE_NAME].value == 'abc123'


def test_leaves_a_matching_hint_alone():
    response = _process_response(
        cookies={FORMPLAYER_SESSION_COOKIE_NAME: 'abc123'},
        couch_user=SimpleNamespace(user_id='abc123'),
    )

    assert FORMPLAYER_SESSION_COOKIE_NAME not in response.cookies


def test_routes_a_public_form_session_on_its_own_id():
    session = SimpleNamespace(id=uuid4())

    response = _process_response(public_form_session=session)

    assert response.cookies[FORMPLAYER_SESSION_COOKIE_NAME].value == session.id.hex


def test_a_public_form_session_never_routes_on_its_user():
    # every public form session reports the same user id, so routing on it
    # would hash them all onto one formplayer machine
    session = SimpleNamespace(id=uuid4())

    response = _process_response(
        couch_user=SimpleNamespace(user_id=PUBLIC_USER_ID),
        public_form_session=session,
    )

    assert response.cookies[FORMPLAYER_SESSION_COOKIE_NAME].value == session.id.hex


def test_a_public_form_session_does_not_move_an_already_routed_browser():
    response = _process_response(
        cookies={FORMPLAYER_SESSION_COOKIE_NAME: 'signed-in-elsewhere'},
        public_form_session=SimpleNamespace(id=uuid4()),
    )

    assert FORMPLAYER_SESSION_COOKIE_NAME not in response.cookies


def test_an_unauthenticated_request_is_left_alone():
    response = _process_response()

    assert FORMPLAYER_SESSION_COOKIE_NAME not in response.cookies
