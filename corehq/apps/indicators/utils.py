from couchdbkit import ResourceNotFound
from dimagi.utils.couch.database import get_db


def get_indicator_config():
    try:
        return get_db().get('INDICATOR_CONFIGURATION').get('namespaces', {})
    except ResourceNotFound:
        pass
    return {}


def get_namespaces(domain, as_choices=False):
    available_namespaces = get_indicator_config()
    return available_namespaces.get(domain, ()) if as_choices else [n[0] for n in available_namespaces.get(domain, [])]


def get_namespace_name(domain, namespace):
    namespaces = get_namespaces(domain, as_choices=True)
    namespaces = dict(namespaces)
    return namespaces.get(namespace)


def get_indicator_domains():
    return get_indicator_config().keys()
