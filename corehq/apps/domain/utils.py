import re

from couchdbkit import ResourceNotFound
from django.conf import settings

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.util.quickcache import quickcache
from dimagi.utils.couch.database import get_db
from corehq.apps.es import DomainES


DOMAIN_MODULE_KEY = 'DOMAIN_MODULE_CONFIG'
ADM_DOMAIN_KEY = 'ADM_ENABLED_DOMAINS'

new_domain_re = r"(?:[a-z0-9]+\-)*[a-z0-9]+" # lowercase letters, numbers, and '-' (at most one between "words")

grandfathered_domain_re = r"[a-z0-9\-\.:]+"
legacy_domain_re = r"[\w\.:-]+"
commcare_public_domain_url = '/a/public/'
website_re = '(http(s?)\:\/\/|~/|/)?([a-zA-Z]{1}([\w\-]+\.)+([\w]{2,5}))(:[\d]{1,5})?/?(\w+\.[\w]{3,4})?((\?\w+=\w+)?(&\w+=\w+)*)?'


def normalize_domain_name(domain):
    if domain:
        normalized = domain.replace('_', '-').lower()
        if settings.DEBUG:
            assert(re.match('^%s$' % grandfathered_domain_re, normalized))
        return normalized
    return domain


def get_domained_url(domain, path):
    return '/a/%s/%s' % (domain, path)


def get_domain_from_url(path):
    try:
        domain, = re.compile(r'^/a/(?P<domain>%s)/' % legacy_domain_re).search(path).groups()
    except Exception:
        domain = None
    return domain


@quickcache([], timeout=60)
def get_domain_module_map():
    hardcoded = getattr(settings, 'DOMAIN_MODULE_MAP', {})
    try:
        dynamic = get_db().open_doc('DOMAIN_MODULE_CONFIG').get('module_map', {})
    except ResourceNotFound:
        dynamic = {}

    hardcoded.update(dynamic)
    return hardcoded


@quickcache(['domain'])
def domain_restricts_superusers(domain):
    domain = Domain.get_by_name(domain)
    if not domain:
        return False
    return domain.restrict_superusers


def get_dummy_domain(domain_type=None):
    domain_type = domain_type or 'commcare'
    dummy_domain = Domain()
    dummy_domain.commtrack_enabled = (domain_type == 'commtrack')
    return dummy_domain


def user_has_custom_top_menu(domain_name, couch_user):
    """
    This is currently used for a one-off custom case (ewsghana, ilsgateway)
    that required to be a toggle instead of a custom domain module setting
    """
    return (toggles.CUSTOM_MENU_BAR.enabled(domain_name) and
            not couch_user.is_superuser)


def get_domains_created_by_user(creating_user):
    query = DomainES().created_by_user(creating_user)
    data = query.run()
    return [d['name'] for d in data.hits]
