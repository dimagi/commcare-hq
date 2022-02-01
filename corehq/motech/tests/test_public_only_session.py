from contextlib import contextmanager
from functools import wraps

import requests
from testil import assert_raises, eq

from corehq.motech.auth import make_session_public_only
from corehq.util.urlvalidate.urlvalidate import PossibleSSRFAttempt


def test_public_only_session__simple_success():
    session = _set_up_session()
    response = session.get('https://example.com/')
    eq(response.status_code, 200)


def test_public_only_session__simple_invalid_url_local():
    session = _set_up_session()
    with assert_raises(PossibleSSRFAttempt):
        session.get('http://localhost')


def test_public_only_session__simple_invalid_url_private():
    session = _set_up_session()
    with assert_raises(PossibleSSRFAttempt):
        session.get('http://10.0.0.0')


def test_public_only_session__redirect_to_valid_url():
    session = _set_up_session()
    with _patch_session_with_hard_coded_response(session, 'https://myredirect.com/',
                                                 _get_redirect_response('https://example.com/')):
        response = session.get('https://myredirect.com/')
        eq(response.status_code, 200)


def test_public_only_session__redirect_to_invalid_url_local():
    session = _set_up_session()

    with _patch_session_with_hard_coded_response(session, 'https://myredirect.com/',
                                                 _get_redirect_response('http://localhost')):
        with assert_raises(PossibleSSRFAttempt):
            session.get('https://myredirect.com/')


def test_public_only_session__redirect_to_invalid_url_local_private():
    session = _set_up_session()

    with _patch_session_with_hard_coded_response(session, 'https://myredirect.com/',
                                                 _get_redirect_response('http://10.0.0.0')):
        with assert_raises(PossibleSSRFAttempt):
            session.get('https://myredirect.com/')


def _set_up_session():
    session = requests.Session()
    make_session_public_only(session, 'demo_domain', src='testing')
    return session


def _get_redirect_response(redirect_location):
    """
    Get a requests.Response object that is a 301 Redirect to `redirect_location`
    """
    response = requests.Response()
    response.status_code = 301
    response.headers['Location'] = redirect_location
    return response


@contextmanager
def _patch_session_with_hard_coded_response(session, url, response):
    """
    Hard-code a response in a requests.Session object

    Patches `session` such that any calls made to `session.get`, `session.post`, etc. for `url`
    will immediately return hard-coded `response` rather than making any real HTTP requests.
    with _patch_session_with_hard_coded_response(session, url, response):
        ...
        session.get(url)  # return hard-coded `response`
        ...
    """
    def _make_send(original_send):
        @wraps(original_send)
        def send(request, **kwargs):
            if request.url == url:
                return response
            else:
                return original_send(request, **kwargs)
        send._original_send = original_send
        return send

    for key, adapter in session.adapters.items():
        if url.startswith(key):
            adapter.send = _make_send(adapter.send)

    yield session

    for key, adapter in session.adapters.items():
        if url.startswith(key):
            adapter.send = adapter.send._original_send
