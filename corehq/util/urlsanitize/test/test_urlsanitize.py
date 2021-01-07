import ipaddress
import socket

from ..urlsanitize import PossibleSSRFAttempt, sanitize_user_input_url, CannotResolveHost, InvalidURL

RAISE = object()
RETURN = object()

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
    ('http://A.8.8.8.8.1time.169.254.169.254.1time.repeat.rebind.network/', (RAISE, PossibleSSRFAttempt('is_link_local'))),
    ('http://10.124.10.11', (RAISE, PossibleSSRFAttempt('is_private'))),
    ('some-non-url', (RAISE, InvalidURL())),
]


def test_example_suite():
    for input_url, (result, value) in SUITE:
        print(input_url)
        if result is RETURN:
            assert sanitize_user_input_url(input_url) == value, \
                f"sanitize_url({input_url!r}) should be {value!r} was {sanitize_user_input_url(input_url)}"
        elif result is RAISE:
            try:
                sanitize_user_input_url(input_url)
            except value.__class__ as e:
                assert str(e) == str(value), \
                    f"sanitize_url({input_url!r} should raise {value.__class__.__name__}({str(value)}) raised {value.__class__.__name__}({str(e)})"
        else:
            raise Exception("result in suite should be RETURN or RAISE")


if __name__ == '__main__':
    test_example_suite()
