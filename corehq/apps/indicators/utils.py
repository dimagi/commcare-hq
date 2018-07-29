from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import ResourceNotFound
from django.conf import settings
from corehq.util.quickcache import quickcache
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.database import get_db


INDICATOR_CONFIG_DOC_ID = 'INDICATOR_CONFIGURATION'
INDICATOR_CONFIG_LOCK_KEY = 'udpate-indicator-configuration-doc'


@quickcache([], timeout=60)
def get_indicator_config():
    try:
        doc = get_db().open_doc(INDICATOR_CONFIG_DOC_ID)
    except ResourceNotFound:
        return {}
    else:
        return doc.get('namespaces', {})


def set_domain_namespace_entry(domain, entry):
    with CriticalSection([INDICATOR_CONFIG_LOCK_KEY]):
        try:
            doc = get_db().open_doc(INDICATOR_CONFIG_DOC_ID)
        except ResourceNotFound:
            doc = {
                '_id': INDICATOR_CONFIG_DOC_ID,
            }

        if 'namespaces' not in doc:
            doc['namespaces'] = {}

        doc['namespaces'][domain] = entry
        get_db().save_doc(doc)
        get_indicator_config.clear()


def get_namespaces(domain, as_choices=False):
    available_namespaces = get_indicator_config()
    if as_choices:
        return available_namespaces.get(domain, ())
    else:
        return [n[0] for n in available_namespaces.get(domain, [])]


def get_namespace_name(domain, namespace):
    namespaces = get_namespaces(domain, as_choices=True)
    namespaces = dict(namespaces)
    return namespaces.get(namespace)


def get_indicator_domains():
    return list(get_indicator_config())


def get_mvp_domains():
    from mvp.models import MVP
    if settings.UNIT_TESTING:
        return MVP.DOMAINS
    return get_indicator_domains() or MVP.DOMAINS
