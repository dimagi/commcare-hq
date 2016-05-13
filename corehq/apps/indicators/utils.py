from couchdbkit import ResourceNotFound
from django.conf import settings
from corehq.util.quickcache import quickcache
from corehq.util.test_utils import unit_testing_only
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.database import get_db


@quickcache([], timeout=60)
def get_indicator_config():
    try:
        doc = get_db().open_doc('INDICATOR_CONFIGURATION')
    except ResourceNotFound:
        return {}
    else:
        return doc.get('namespaces', {})


def set_domain_namespace_entry(domain, entry):
    with CriticalSection(['udpate-indicator-configuration-doc']):
        try:
            doc = get_db().open_doc('INDICATOR_CONFIGURATION')
        except ResourceNotFound:
            doc = {
                '_id': 'INDICATOR_CONFIGURATION',
            }

        if 'namespaces' not in doc:
            doc['namespaces'] = {}

        doc['namespaces'][domain] = entry
        get_db().save_doc(doc)
        get_indicator_config.clear()


@unit_testing_only
def delete_indicator_doc():
    with CriticalSection(['udpate-indicator-configuration-doc']):
        try:
            get_db().delete_doc('INDICATOR_CONFIGURATION')
            get_indicator_config.clear()
        except ResourceNotFound:
            pass


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
    return get_indicator_config().keys()


def get_mvp_domains():
    from mvp.models import MVP
    if settings.UNIT_TESTING:
        return MVP.DOMAINS
    return get_indicator_domains() or MVP.DOMAINS
