import re

from corehq.util.urlvalidate.urlvalidate import validate_user_input_url, InvalidURL, PossibleSSRFAttempt

BANNED_HOST_REGEX = (
    r'commcarehq\.org',
    r'10\..*\..*\..*',
    r'172.1[6-9]\..*\..*',
    r'172.2[0-9]\..*\..*',
    r'172.3[0-1]\..*\..*',
    r'192.168\..*\..*',
    r'127.0.0.1',
    r'localhost',
)


def is_url_or_host_banned(url_or_host):
    # We should never be accepting user-entered urls that we then connect to, and
    # all urls should always be configured only by site admins. However, we can
    # use this check to help site admins ensure they're not making any obvious
    # mistakes.
    black_list_result = any([re.search(regex, url_or_host) for regex in BANNED_HOST_REGEX])
    if black_list_result:
        return True

    url = url_or_host if has_scheme(url_or_host) else f'http://{url_or_host}'
    try:
        validate_user_input_url(url)
        return False
    except (InvalidURL, PossibleSSRFAttempt):
        return True


def has_scheme(url):
    scheme_regex = r'(?:.+:)?//'  # Should match 'http://', 'file://', '//' etc
    return bool(re.match(scheme_regex, url))
