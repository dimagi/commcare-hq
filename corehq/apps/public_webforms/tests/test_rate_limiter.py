from unittest import mock
from uuid import uuid4

from unmagic import fixture, use

from corehq.apps.public_webforms.rate_limiter import (
    link_requests_per_contact,
    rate_limit_link_request,
)


@fixture
def limiter_on():
    with mock.patch(
        'corehq.apps.public_webforms.rate_limiter'
        '.SHOULD_RATE_LIMIT_LINK_REQUESTS', True
    ):
        yield


def _a_contact():
    return f'{uuid4().hex}@example.com'


def _requests_allowed_per_hour():
    return next(
        limit
        for __, limits in link_requests_per_contact.get_rate_limits('')
        for counter, limit in limits
        if counter.key == 'hour'
    )


@use(limiter_on)
def test_contact_rate_limiter_allows_multiple_requests():
    # a respondent who did not receive the first message asks a second time
    contact = _a_contact()

    assert rate_limit_link_request(contact) is False
    assert rate_limit_link_request(contact) is False


@use(limiter_on)
def test_contact_rate_limiter_blocks_too_many_requests():
    contact = _a_contact()

    for __ in range(_requests_allowed_per_hour()):
        assert rate_limit_link_request(contact) is False

    assert rate_limit_link_request(contact) is True
