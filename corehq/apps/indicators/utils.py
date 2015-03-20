from couchdbkit import ResourceNotFound
from corehq.util.quickcache import quickcache
from dimagi.utils.couch.database import get_db


@quickcache([], timeout=60)
def get_indicator_config():
    try:
        doc = get_db().open_doc('INDICATOR_CONFIGURATION')
    except ResourceNotFound:
        return {}
    else:
        return doc.get('namespaces', {})


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
