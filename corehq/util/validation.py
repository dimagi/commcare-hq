from __future__ import absolute_import
from __future__ import unicode_literals
import re


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
    return any([re.search(regex, url_or_host) for regex in BANNED_HOST_REGEX])
