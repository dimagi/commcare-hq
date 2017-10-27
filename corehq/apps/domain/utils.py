from collections import Counter
import os
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
domain_url_re = re.compile(r'^/a/(?P<domain>%s)/' % legacy_domain_re)


def normalize_domain_name(domain):
    if domain:
        normalized = domain.replace('_', '-').lower()
        if settings.DEBUG:
            assert(re.match('^%s$' % grandfathered_domain_re, normalized))
        return normalized
    return domain


def get_domain_from_url(path):
    try:
        domain, = domain_url_re.search(path).groups()
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


@quickcache([], timeout=3600)
def domain_name_stop_words():
    path = os.path.join(os.path.dirname(__file__), 'static', 'domain', 'json')
    with open(os.path.join(path, 'stop_words.yml')) as f:
        return tuple([word.strip() for word in f.readlines() if word[0] != '#'])


def get_domain_url_slug(hr_name, max_length=25, separator='-'):
    from dimagi.utils.name_to_url import name_to_url
    name = name_to_url(hr_name, "project")
    if len(name) <= max_length:
        return name

    stop_words = domain_name_stop_words()
    words = [word for word in name.split('-') if word not in stop_words]
    words = iter(words)
    try:
        text = next(words)
    except StopIteration:
        return u''

    for word in words:
        if len(text + separator + word) <= max_length:
            text += separator + word

    return text[:max_length]


def guess_domain_language(domain_name):
    """
    A domain does not have a default language, but its apps do. Return
    the language code of the most common default language across apps.
    """
    domain = Domain.get_by_name(domain_name)
    counter = Counter([app.default_language for app in domain.applications() if not app.is_remote_app()])
    return counter.most_common(1)[0][0] if counter else 'en'
