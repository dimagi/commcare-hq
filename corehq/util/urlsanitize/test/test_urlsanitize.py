import ipaddress
import socket

from testil import eq, assert_raises

from ..urlsanitize import PossibleSSRFAttempt, sanitize_user_input_url, CannotResolveHost, InvalidURL

RAISE = object()
RETURN = object()

GOOGLE_IP = SUITE = None  # set in setup_module


def setup_module():
    global GOOGLE_IP, SUITE

    GOOGLE_IP = ipaddress.ip_address(socket.gethostbyname('google.com'))
    SUITE = [
        ('https://google.com/', (RETURN, GOOGLE_IP)),
        ('http://google.com/', (RETURN, GOOGLE_IP)),
        ('http://google.com', (RETURN, GOOGLE_IP)),
        ('http://foo.example.com/', (RAISE, CannotResolveHost())),
        ('http://localhost/', (RAISE, PossibleSSRFAttempt('is_loopback'))),
        ('http://Localhost/', (RAISE, PossibleSSRFAttempt('is_loopback'))),
        ('http://169.254.169.254/latest/meta-data', (RAISE, PossibleSSRFAttempt('is_link_local'))),
        ('http://2852039166/', (RAISE, PossibleSSRFAttempt('is_link_local'))),
        ('http://7147006462/', (RAISE, PossibleSSRFAttempt('is_link_local'))),
        ('http://0xA9.0xFE.0xA9.0xFE/', (RAISE, PossibleSSRFAttempt('is_link_local'))),
        ('http://0x41414141A9FEA9FE/', (RAISE, PossibleSSRFAttempt('is_link_local'))),
        ('http://0xA9FEA9FE/', (RAISE, PossibleSSRFAttempt('is_link_local'))),
        ('http://0251.0376.0251.0376/', (RAISE, PossibleSSRFAttempt('is_link_local'))),
        ('http://0251.00376.000251.0000376/', (RAISE, PossibleSSRFAttempt('is_link_local'))),
        ('http://169.254.169.254.xip.io/', (RAISE, PossibleSSRFAttempt('is_link_local'))),
        ('http://10.124.10.11', (RAISE, PossibleSSRFAttempt('is_private'))),
        ('some-non-url', (RAISE, InvalidURL())),
    ]


def test_example_suite():
    for input_url, (result, value) in SUITE:
        print(input_url)

        if result is RETURN:
            eq(sanitize_user_input_url(input_url), value)
        elif result is RAISE:
            if type(value) == PossibleSSRFAttempt:
                with assert_raises(PossibleSSRFAttempt, msg=lambda e: eq(e.reason, value.reason)):
                    sanitize_user_input_url(input_url)
            else:
                with assert_raises(type(value), msg=str(value)):
                    sanitize_user_input_url(input_url)
        else:
            raise Exception("result in suite should be RETURN or RAISE")


def test_rebinding():
    """
    this test doesn't do much, it just checks that a known rebinding endpoint
    and checks the output is one of the two expected values
    """
    url = 'http://A.8.8.8.8.1time.169.254.169.254.1time.repeat.rebind.network/'
    try:
        eq(sanitize_user_input_url(url), ipaddress.IPv4Address('8.8.8.8'))  # this is one possible output
    except PossibleSSRFAttempt as e:
        eq(e.reason, 'is_link_local')
