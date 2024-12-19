from django.test import SimpleTestCase

import pytest
from testil import assert_raises, eq

from ..ip_resolver import CannotResolveHost
from ..urlvalidate import (
    InvalidURL,
    PossibleSSRFAttempt,
    validate_user_input_url,
)
from .mockipinfo import hostname_resolving_to_ips

NO_RAISE = object()


@pytest.mark.parametrize("input_url, expected", [
    ('https://google.com/', NO_RAISE),
    ('http://google.com/', NO_RAISE),
    ('http://google.com', NO_RAISE),
    ('http://foo.example.com/', CannotResolveHost('foo.example.com')),
    ('http://localhost/', PossibleSSRFAttempt('is_loopback')),
    ('http://Localhost/', PossibleSSRFAttempt('is_loopback')),
    ('http://169.254.169.254/latest/meta-data', PossibleSSRFAttempt('is_link_local')),
    ('http://2852039166/', PossibleSSRFAttempt('is_link_local')),
    ('http://0xA9.0xFE.0xA9.0xFE/', PossibleSSRFAttempt('is_link_local')),
    ('http://0xA9FEA9FE/', PossibleSSRFAttempt('is_link_local')),
    ('http://0251.0376.0251.0376/', PossibleSSRFAttempt('is_link_local')),
    ('http://0251.00376.000251.0000376/', PossibleSSRFAttempt('is_link_local')),
    ('http://10.124.10.11', PossibleSSRFAttempt('is_private')),
    ('some-non-url', InvalidURL()),
])
def test_example_urls(input_url, expected):
    if expected is NO_RAISE:
        validate_user_input_url(input_url)
    else:
        assert isinstance(expected, Exception), f"expected exception instance, got {expected!r}"
        if type(expected) is PossibleSSRFAttempt:
            with assert_raises(PossibleSSRFAttempt, msg=lambda e: eq(e.reason, expected.reason)):
                validate_user_input_url(input_url)
        else:
            with assert_raises(type(expected), msg=str(expected)):
                validate_user_input_url(input_url)


def test_rebinding():
    """
    this test doesn't do much, it just checks that a known rebinding endpoint
    is either valid, or pointing to a link local address
    """
    url = 'http://A.8.8.8.8.1time.169.254.169.254.1time.repeat.rebind.network/'
    try:
        validate_user_input_url(url)
    except PossibleSSRFAttempt as e:
        eq(e.reason, 'is_link_local')


class SanitizeIPv6Tests(SimpleTestCase):
    def test_valid_ipv6_address_is_accepted(self):
        ip_text = '2607:f8b0:4006:806::2004'
        valid_ipv6 = f'http://[{ip_text}]'
        validate_user_input_url(valid_ipv6)

    def test_recognizes_empty_ipv6_as_ssrf_attempt(self):
        with self.assertRaises(PossibleSSRFAttempt) as cm:
            validate_user_input_url('http://[::]')

        self.assertEqual(cm.exception.reason, 'is_reserved')

    def test_recognizes_all_zeros_as_ssrf_attempt(self):
        with self.assertRaises(PossibleSSRFAttempt) as cm:
            validate_user_input_url('http://[0000:0000:0000:0000:0000:0000:0000:0000]')

        self.assertEqual(cm.exception.reason, 'is_reserved')

    def test_recognizes_trailing_one_as_ssrf_attempt(self):
        with self.assertRaises(PossibleSSRFAttempt) as cm:
            validate_user_input_url('http://[::1]')

        self.assertEqual(cm.exception.reason, 'is_loopback')

    def test_address_with_port_can_cause_ssrf(self):
        with self.assertRaises(PossibleSSRFAttempt):
            validate_user_input_url('http://[::]:22')


class SanitizeMultiIPTests(SimpleTestCase):
    VALID_IP_1 = '172.217.12.206'
    VALID_IP_2 = '98.137.11.164'
    VALID_IP_3 = '74.6.231.21'

    VALID_IPv6 = '2607:f8b0:4006:806::2004'

    LOOPBACK_ADDRESS = '127.0.0.1'

    def test_when_all_addresses_are_valid_does_not_raise_exception(self):
        with hostname_resolving_to_ips('test_address', [self.VALID_IP_1, self.VALID_IP_2, self.VALID_IP_3]):
            validate_user_input_url('http://test_addresss')

    def test_when_any_address_is_invalid_an_exception_is_raised(self):
        with hostname_resolving_to_ips(
            'some.malicious.url',
            [self.VALID_IP_1, self.LOOPBACK_ADDRESS, self.VALID_IP_3]
        ):
            with self.assertRaises(PossibleSSRFAttempt):
                validate_user_input_url('http://some.malicious.url')

    def test_mixed_valid_addresses_do_not_raise_exception(self):
        with hostname_resolving_to_ips('test_address', [self.VALID_IPv6, self.VALID_IP_1]):
            validate_user_input_url('http://test_address')
