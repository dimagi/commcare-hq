import re
from django.conf import settings

new_domain_re = r"(?:[a-z0-9]+\-)*[a-z0-9]+" # lowercase letters, numbers, and '-' (at most one between "words")
grandfathered_domain_re = r"[a-z0-9\-\.]+"
legacy_domain_re = r"[\w\.-]+"

def normalize_domain_name(domain):
    normalized = domain.replace('_', '-').lower()
    if settings.DEBUG:
        assert(re.match('^%s$' % grandfathered_domain_re, normalized))
    return normalized

def get_domained_url(domain, path):
    return '/a/%s/%s' % (domain, path)