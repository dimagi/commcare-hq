from django.conf import settings


def get_namespaces(domain, as_choices=False):
    available_namespaces = getattr(settings, 'INDICATOR_NAMESPACES', {})
    return available_namespaces.get(domain, ()) if as_choices else [n[0] for n in available_namespaces.get(domain, [])]

def get_namespace_name(domain, namespace):
    namespaces = get_namespaces(domain, as_choices=True)
    namespaces = dict(namespaces)
    return namespaces.get(namespace)
