from unittest import mock
from uuid import uuid4

from django.test import RequestFactory

from unmagic import fixture, use

from corehq.apps.public_webforms.rate_limiter import (
    link_requests_global,
    link_requests_per_contact,
    link_requests_per_ip,
    rate_limit_link_request,
)
from corehq.util.global_request.api import set_request


@fixture
def limiter_on():
    """The limiter is off under test, so a test that wants it says so."""
    set_request(RequestFactory().post('/', REMOTE_ADDR='203.0.113.7'))
    try:
        with mock.patch(
            'corehq.apps.public_webforms.rate_limiter'
            '.SHOULD_RATE_LIMIT_LINK_REQUESTS', True
        ):
            yield
    finally:
        set_request(None)


def _a_contact():
    return f'{uuid4().hex}@example.com'


def _requests_allowed_per_hour():
    return next(
        limit
        for __, limits in link_requests_per_contact.get_rate_limits('')
        for counter, limit in limits
        if counter.key == 'hour'
    )


def _exhausted(limiter):
    """Stand in for a limiter whose hourly window is already spent.

    The IP and global limits are too large to reach by making real requests,
    so what is checked is that they are consulted at all.
    """
    return mock.patch.object(
        limiter, 'get_window_of_first_exceeded_limit', return_value='hour')


@use('db', limiter_on)
def test_contact_rate_limiter_allows_multiple_requests():
    # a respondent who did not receive the first message asks a second time
    contact = _a_contact()

    assert rate_limit_link_request(contact) is False
    assert rate_limit_link_request(contact) is False


@use('db', limiter_on)
def test_contact_rate_limiter_blocks_too_many_requests():
    contact = _a_contact()

    for __ in range(_requests_allowed_per_hour()):
        assert rate_limit_link_request(contact) is False

    assert rate_limit_link_request(contact) is True


@use('db', limiter_on)
def test_exhausted_ip_limit_blocks_requests_based_on_ip():
    with _exhausted(link_requests_per_ip) as exceeded:
        assert rate_limit_link_request(_a_contact()) is True

    # the address the request came from, not the contact it named
    assert exceeded.call_args.args == ('ip:203.0.113.7',)


@use('db', limiter_on)
def test_exhausted_global_limit_blocks_everything():
    with _exhausted(link_requests_global):
        assert rate_limit_link_request(_a_contact()) is True


@use('db', limiter_on)
def test_accepted_request_counts_toward_all_limits():
    contact = _a_contact()

    with (
        mock.patch.object(link_requests_global, 'report_usage') as globally,
        mock.patch.object(link_requests_per_ip, 'report_usage') as per_ip,
        mock.patch.object(link_requests_per_contact, 'report_usage') as per_contact,
    ):
        rate_limit_link_request(contact)

    assert globally.called
    assert per_ip.call_args.args == ('ip:203.0.113.7',)
    assert per_contact.call_args.args == (f'contact:{contact}',)


@use('db', limiter_on)
def test_refused_request_does_not_count_toward_limits():
    with _exhausted(link_requests_global):
        with mock.patch.object(
            link_requests_per_contact, 'report_usage'
        ) as per_contact:
            rate_limit_link_request(_a_contact())

    assert not per_contact.called
