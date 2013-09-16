import re
from couchdbkit import ResourceNotFound
from django.conf import settings
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.database import get_db
from django.core.cache import cache

DOMAIN_MODULE_KEY = 'DOMAIN_MODULE_CONFIG'
ADM_DOMAIN_KEY = 'ADM_ENABLED_DOMAINS'

new_domain_re = r"(?:[a-z0-9]+\-)*[a-z0-9]+" # lowercase letters, numbers, and '-' (at most one between "words")
new_org_re = r"(?:[a-z0-9]+\-)*[a-zA-Z0-9]+" # lowercase and uppercase letters, numbers, and '-' (at most one between "words")
grandfathered_domain_re = r"[a-z0-9\-\.:]+"
legacy_domain_re = r"[\w\.:-]+"
commcare_public_domain_url = '/a/public/'
website_re = '(http(s?)\:\/\/|~/|/)?([a-zA-Z]{1}([\w\-]+\.)+([\w]{2,5}))(:[\d]{1,5})?/?(\w+\.[\w]{3,4})?((\?\w+=\w+)?(&\w+=\w+)*)?'

def normalize_domain_name(domain):
    normalized = domain.replace('_', '-').lower()
    if settings.DEBUG:
        assert(re.match('^%s$' % grandfathered_domain_re, normalized))
    return normalized

def get_domained_url(domain, path):
    return '/a/%s/%s' % (domain, path)

def get_domain_from_url(path):
    try:
        domain, = re.compile(r'^/a/(?P<domain>%s)/' % legacy_domain_re).search(path).groups()
    except Exception:
        domain = None
    return domain


def get_domain_module_map():
    hardcoded = getattr(settings, 'DOMAIN_MODULE_MAP', {})

    try:
        dynamic = cache_core.cached_open_doc(get_db(), 'DOMAIN_MODULE_CONFIG').get('module_map', {})
    except ResourceNotFound:
        dynamic = {}

    hardcoded.update(dynamic)
    return hardcoded


def get_adm_enabled_domains():
    try:

        #cache_core GET
        domains = cache_core.cached_open_doc(get_db(), 'ADM_ENABLED_DOMAINS').get('domains', {})
        #domains = get_db().get('ADM_ENABLED_DOMAINS').get('domains', [])
    except ResourceNotFound:
        domains = []
    return domains
