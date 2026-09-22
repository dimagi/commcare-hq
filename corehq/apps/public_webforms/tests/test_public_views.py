import datetime
from unittest import mock
from uuid import uuid4

from django.test import Client
from django.urls import reverse
from django.utils import timezone

import pytest
from unmagic import fixture, use

from corehq.apps.public_webforms.models import PublicFormSession
from corehq.apps.public_webforms.decorators import (
    PUBLIC_FORM_SESSION_COOKIE_NAME,
)
from corehq.apps.public_webforms.public.views import (
    PublicFormSubmittedView,
    PublicFormView,
    PublicWebformLinkSentView,
    PublicWebformRequestView,
)
from corehq.apps.public_webforms.tests.utils import (
    create_session,
    create_webform,
    public_webforms_available,
    skip_turnstile,
)


def _url(urlname, public_id):
    return reverse(urlname, kwargs={'public_id': public_id.hex})


def _get(public_id):
    return Client().get(_url(PublicWebformRequestView.urlname, public_id))


def _request_a_link(public_id, **fields):
    return Client().post(_url(PublicWebformRequestView.urlname, public_id), {
        'delivery': 'email',
        'email': 'respondent@example.com',
        **fields,
    })


@use('db', public_webforms_available)
@pytest.mark.parametrize('expires_in, is_disabled', [
    (datetime.timedelta(days=1), True),
    (datetime.timedelta(days=-1), False),
    (datetime.timedelta(days=-1), True),
], ids=['closed', 'expired', 'expired-and-closed'])
def test_a_webform_not_accepting_requests_says_so(expires_in, is_disabled):
    webform = create_webform(
        expires_at=timezone.now() + expires_in, is_disabled=is_disabled)

    response = _get(webform.public_id)

    assert response.status_code == 404
    # the respondent is told the link is dead, not left with a bare 404
    assert b'Requests Closed' in response.content


@use('db', public_webforms_available)
def test_an_unknown_link_is_not_found():
    response = _get(uuid4())

    assert response.status_code == 404
    assert b'Requests Closed' not in response.content


@use('db', public_webforms_available, skip_turnstile)
def test_a_request_to_a_webform_not_accepting_requests_creates_no_session():
    webform = create_webform(is_disabled=True)

    response = _request_a_link(webform.public_id)

    assert b'Requests Closed' in response.content
    assert not PublicFormSession.objects.filter(public_webform=webform).exists()


@use('db', public_webforms_available, skip_turnstile)
def test_a_requested_link_redirects_to_a_page_saying_it_was_sent():
    webform = create_webform(is_disabled=False)
    with mock.patch('corehq.apps.public_webforms.public.views.get_app', return_value=None):
        response = _request_a_link(webform.public_id)

    assert response.status_code == 302
    assert response.url == _url(
        PublicWebformLinkSentView.urlname, webform.public_id)


@use('db', public_webforms_available, skip_turnstile)
def test_a_requested_link_is_sent():
    webform = create_webform(is_disabled=False)

    with (
        mock.patch('corehq.apps.public_webforms.public.views.get_app', return_value=None),
        mock.patch('corehq.apps.public_webforms.public.views.send_one_time_link') as send
    ):
        _request_a_link(webform.public_id, email='someone@example.com')

    session = PublicFormSession.objects.get(public_webform=webform)
    assert send.call_args.args[0] == session


@fixture
def stub_app_doc():
    with mock.patch(
        'corehq.apps.public_webforms.public.views.get_app_doc',
        return_value={'_id': 'build', 'name': 'Antenatal visit', 'langs': ['en']},
    ):
        yield


def _open_form(public_id, session_id):
    return Client().get(reverse(PublicFormView.urlname, kwargs={
        'public_id': public_id.hex, 'session_id': session_id}))


@use('db', public_webforms_available, stub_app_doc)
def test_public_form_page_context():
    session = create_session(create_webform(), email='respondent@example.com')

    response = _open_form(session.public_webform.public_id, session.id.hex)
    assert response.context['app_build_id'] == session.public_webform.app_build_id
    assert response.context['endpoint_id'] == session.public_webform.endpoint_id
    assert response.context['toggles_dict'] is not None
    assert response.context['previews_dict'] is not None
    assert response.context['submitted_url'] == reverse(
        PublicFormSubmittedView.urlname,
        kwargs={'public_id': session.public_webform.public_id.hex})


@use('db', public_webforms_available, stub_app_doc)
def test_opening_a_one_time_link_sets_public_session_key_cookie():
    session = create_session(create_webform(), email='respondent@example.com')

    response = _open_form(session.public_webform.public_id, session.id.hex)

    cookie = response.cookies[PUBLIC_FORM_SESSION_COOKIE_NAME]
    assert cookie.value == session.session_key.hex
    assert cookie['httponly']
    assert cookie['samesite'] == 'Lax'


@use('db', public_webforms_available, stub_app_doc)
def test_opening_a_one_time_link_records_when_it_was_opened():
    session = create_session(create_webform(), email='respondent@example.com')

    _open_form(session.public_webform.public_id, session.id.hex)

    session.refresh_from_db()
    assert session.opened_at is not None
