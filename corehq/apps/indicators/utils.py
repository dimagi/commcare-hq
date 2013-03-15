from couchdbkit import ResourceNotFound
from dimagi.utils.couch.database import get_db


def get_namespaces(domain, as_choices=False):
    try:
        available_namespaces = get_db().get('INDICATOR_CONFIGURATION').get('namespaces', {})
        return available_namespaces.get(domain, ()) if as_choices else [n[0] for n in available_namespaces.get(domain, [])]
    except ResourceNotFound:
        pass
    return []


def get_namespace_name(domain, namespace):
    namespaces = get_namespaces(domain, as_choices=True)
    namespaces = dict(namespaces)
    return namespaces.get(namespace)


def get_indicator_domains():
    try:
        return get_db().get('INDICATOR_CONFIGURATION').get('enabled_domains', [])
    except ResourceNotFound:
        pass
    return []
