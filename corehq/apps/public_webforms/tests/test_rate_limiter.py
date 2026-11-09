from datetime import datetime
from unittest import mock
from uuid import uuid4

import pytest
from django.test import RequestFactory
from time_machine import travel

from unmagic import fixture, use

from corehq.apps.public_webforms.rate_limiter import (
    STATUS_ACCEPTED,
    STATUS_DOMAIN_RATE_LIMITED,
    STATUS_GLOBAL_RATE_LIMITED,
    STATUS_IP_RATE_LIMITED,
    _check_for_exceeded_soft_rate_limits,
    access_requests_global,
    access_requests_per_contact,
    access_requests_per_domain,
    access_requests_per_ip,
    rate_limit_access_request,
    rate_limit_session_request,
    requests_per_session,
    soft_access_requests_global,
    soft_access_requests_per_domain,
    soft_access_requests_per_ip,
)
from corehq.util.global_request.api import set_request


@fixture
def limiter_on():
    """The limiter is off under test, so a test that wants it says so."""
    set_request(RequestFactory().post('/', REMOTE_ADDR='203.0.113.7'))
    try:
        with mock.patch(
            'corehq.apps.public_webforms.rate_limiter'
            '.SHOULD_RATE_LIMIT_ACCESS_REQUESTS', True
        ):
            yield
    finally:
        set_request(None)


def _a_contact():
    return f'{uuid4().hex}@example.com'


def _a_domain():
    return f'project-{uuid4().hex}'


def _requests_allowed_per_hour():
    return next(
        limit
        for __, limits in access_requests_per_contact.get_rate_limits('')
        for counter, limit in limits
        if counter.key == 'hour'
    )


def _session_requests_allowed_per_second():
    return next(
        limit
        for __, limits in requests_per_session.get_rate_limits('')
        for counter, limit in limits
        if counter.key == 'second'
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
    domain = _a_domain()

    assert rate_limit_access_request(domain, contact) is False
    assert rate_limit_access_request(domain, contact) is False


@use('db', limiter_on)
def test_contact_rate_limiter_blocks_too_many_requests():
    contact = _a_contact()
    domain = _a_domain()

    for __ in range(_requests_allowed_per_hour()):
        assert rate_limit_access_request(domain, contact) is False

    assert rate_limit_access_request(domain, contact) is True


@use('db', limiter_on)
def test_exhausted_domain_limit_blocks_requests_based_on_domain():
    domain = _a_domain()

    with _exhausted(access_requests_per_domain) as exceeded:
        assert rate_limit_access_request(domain, _a_contact()) is True

    assert exceeded.call_args.args == (f'domain:{domain}',)


@use('db', limiter_on)
def test_exhausted_ip_limit_blocks_requests_based_on_ip():
    with _exhausted(access_requests_per_ip) as exceeded:
        assert rate_limit_access_request(_a_domain(), _a_contact()) is True

    # the address the request came from, not the contact it named
    assert exceeded.call_args.args == ('ip:203.0.113.7',)


@use('db', limiter_on)
def test_exhausted_global_limit_blocks_everything():
    with _exhausted(access_requests_global):
        assert rate_limit_access_request(_a_domain(), _a_contact()) is True


@use('db', limiter_on)
def test_accepted_request_counts_toward_all_limits():
    contact = _a_contact()
    domain = _a_domain()

    with (
        mock.patch.object(access_requests_global, 'report_usage') as globally,
        mock.patch.object(access_requests_per_domain, 'report_usage') as per_domain,
        mock.patch.object(access_requests_per_ip, 'report_usage') as per_ip,
        mock.patch.object(access_requests_per_contact, 'report_usage') as per_contact,
        mock.patch.object(soft_access_requests_global, 'report_usage') as soft_globally,
        mock.patch.object(soft_access_requests_per_domain, 'report_usage') as soft_per_domain,
        mock.patch.object(soft_access_requests_per_ip, 'report_usage') as soft_per_ip,
    ):
        rate_limit_access_request(domain, contact)

    assert globally.called
    assert per_domain.call_args.args == (f'domain:{domain}',)
    assert per_ip.call_args.args == ('ip:203.0.113.7',)
    assert per_contact.call_args.args == (f'contact:{contact}',)
    assert soft_globally.called
    assert soft_per_domain.call_args.args == (f'domain:{domain}',)
    assert soft_per_ip.call_args.args == ('ip:203.0.113.7',)


@use('db', limiter_on)
def test_refused_request_does_not_count_toward_limits():
    with _exhausted(access_requests_global):
        with mock.patch.object(
            access_requests_per_contact, 'report_usage'
        ) as per_contact:
            rate_limit_access_request(_a_domain(), _a_contact())

    assert not per_contact.called


@use('db', limiter_on)
def test_refused_request_counts_toward_soft_limits():
    with (
        _exhausted(access_requests_global),
        mock.patch.object(soft_access_requests_global, 'report_usage') as soft_globally,
        mock.patch.object(soft_access_requests_per_domain, 'report_usage') as soft_per_domain,
        mock.patch.object(soft_access_requests_per_ip, 'report_usage') as soft_per_ip,
    ):
        assert rate_limit_access_request(_a_domain(), _a_contact()) is True

    assert soft_globally.called
    assert soft_per_domain.called
    assert soft_per_ip.called


@use('db')
def test_soft_status_is_accepted_under_soft_limits():
    assert _check_for_exceeded_soft_rate_limits(
        _a_domain(), '198.51.100.7') == STATUS_ACCEPTED


@use('db')
@pytest.mark.parametrize('limiter, status, scope', [
    (soft_access_requests_global, STATUS_GLOBAL_RATE_LIMITED, ()),
    (soft_access_requests_per_domain, STATUS_DOMAIN_RATE_LIMITED, ('domain:project',)),
    (soft_access_requests_per_ip, STATUS_IP_RATE_LIMITED, ('ip:198.51.100.7',)),
])
def test_soft_status_names_the_soft_limit_reached(limiter, status, scope):
    with _exhausted(limiter) as exceeded:
        assert _check_for_exceeded_soft_rate_limits(
            'project', '198.51.100.7') == status

    assert exceeded.call_args.args == scope


@use('db')
def test_session_rate_limiter_blocks_requests_over_its_limit():
    session_id = uuid4().hex

    with travel(datetime.now(), tick=False):
        for __ in range(_session_requests_allowed_per_second()):
            assert rate_limit_session_request(session_id) is False

        assert rate_limit_session_request(session_id) is True


@use('db')
def test_refused_session_request_does_not_count_toward_its_limit():
    with (
        _exhausted(requests_per_session),
        mock.patch.object(requests_per_session, 'report_usage') as report_usage,
    ):
        assert rate_limit_session_request(uuid4().hex) is True

    assert not report_usage.called
