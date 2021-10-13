import os
import re
import sys
from collections import Counter
from decimal import Decimal

import simplejson
from django.conf import settings

from memoized import memoized

from corehq.apps.domain.dbaccessors import iter_all_domains_and_deleted_domains_with_name
from corehq.apps.domain.extension_points import custom_domain_module
from corehq.util.test_utils import unit_testing_only

from corehq.apps.domain.models import Domain
from corehq.apps.es import DomainES
from corehq.util.quickcache import quickcache

ADM_DOMAIN_KEY = 'ADM_ENABLED_DOMAINS'

new_domain_re = r"(?:[a-z0-9]+\-)*[a-z0-9]+" # lowercase letters, numbers, and '-' (at most one between "words")

grandfathered_domain_re = r"[a-z0-9\-\.:]+"
legacy_domain_re = r"[\w\.:-]+"
domain_url_re = re.compile(r'^/a/(?P<domain>%s)/' % legacy_domain_re)


@memoized
def get_custom_domain_module(domain):
    if domain in settings.DOMAIN_MODULE_MAP:
        return settings.DOMAIN_MODULE_MAP[domain]

    return custom_domain_module(domain)


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


@quickcache(['domain'])
def domain_restricts_superusers(domain):
    domain_obj = Domain.get_by_name(domain)
    if not domain_obj:
        return False
    return domain_obj.restrict_superusers


def get_domains_created_by_user(creating_user):
    query = DomainES().created_by_user(creating_user)
    data = query.run()
    return [d['name'] for d in data.hits]


@quickcache([], timeout=3600)
def domain_name_stop_words():
    path = os.path.join(os.path.dirname(__file__), 'static', 'domain', 'json')
    with open(os.path.join(path, 'stop_words.yml')) as f:
        return {word.strip() for word in f.readlines() if word[0] != '#'}


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
        return ''

    for word in words:
        if len(text + separator + word) <= max_length:
            text += separator + word

    return text[:max_length]


def guess_domain_language(domain_name):
    """
    A domain does not have a default language, but its apps do. Return
    the language code of the most common default language across apps.
    """
    domain_obj = Domain.get_by_name(domain_name)
    counter = Counter([app.default_language for app in domain_obj.applications() if not app.is_remote_app()])
    return counter.most_common(1)[0][0] if counter else 'en'


def silence_during_tests():
    if settings.UNIT_TESTING:
        return open(os.devnull, 'w')
    else:
        return sys.stdout


@unit_testing_only
def clear_domain_names(*domain_names):
    for domain_names in domain_names:
        for domain in iter_all_domains_and_deleted_domains_with_name(domain_names):
            domain.delete()


def get_serializable_wire_invoice_item_from_request(request):
    general_credit = Decimal(request.POST.get('general_credit', 0))
    if general_credit > 0:
        return [{
            'type': 'General Credits',
            'amount': simplejson.dumps(general_credit, use_decimal=True)
        }]

    return []
