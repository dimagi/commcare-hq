import re
import logging
from django.conf import settings
from django.core.mail import send_mail
from dimagi.utils.web import get_url_base

new_domain_re = r"(?:[a-z0-9]+\-)*[a-z0-9]+" # lowercase letters, numbers, and '-' (at most one between "words")
grandfathered_domain_re = r"[a-z0-9\-\.]+"
legacy_domain_re = r"[\w\.-]+"
commcare_public_domain_url = '/a/public/'

def normalize_domain_name(domain):
    normalized = domain.replace('_', '-').lower()
    if settings.DEBUG:
        assert(re.match('^%s$' % grandfathered_domain_re, normalized))
    return normalized

def get_domained_url(domain, path):
    return '/a/%s/%s' % (domain, path)