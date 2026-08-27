import datetime
from uuid import uuid4

from django.test import Client
from django.urls import reverse
from django.utils import timezone

import pytest
from unmagic import use

from corehq.apps.public_webforms.models import PublicFormSession
from corehq.apps.public_webforms.public.views import PublicWebformRequestView
from corehq.apps.public_webforms.tests.utils import (
    create_webform,
    skip_turnstile,
)


def _url(public_id):
    return reverse(
        PublicWebformRequestView.urlname, kwargs={'public_id': public_id.hex})


def _get(public_id):
    return Client().get(_url(public_id))


def _request_a_link(public_id, **fields):
    return Client().post(_url(public_id), {
        'delivery': 'email',
        'email': 'respondent@example.com',
        **fields,
    })


@use('db')
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


@use('db')
def test_an_unknown_link_is_not_found():
    response = _get(uuid4())

    assert response.status_code == 404
    assert b'Requests Closed' not in response.content


@use('db', skip_turnstile)
def test_a_request_to_a_webform_not_accepting_requests_creates_no_session():
    webform = create_webform(is_disabled=True)

    response = _request_a_link(webform.public_id)

    assert b'Requests Closed' in response.content
    assert not PublicFormSession.objects.filter(public_webform=webform).exists()
