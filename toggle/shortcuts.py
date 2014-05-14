from couchdbkit import ResourceNotFound
from django.core.cache import cache
from .models import Toggle


def toggle_enabled(slug, item, check_cache=True, namespace=None):
    """
    Given a toggle and a username, whether the toggle is enabled for that user
    """
    item = _namespaced_item(item, namespace)
    cache_key = get_toggle_cache_key(slug, item)
    if check_cache:
        from_cache = cache.get(cache_key)
        if from_cache is not None:
            return from_cache
    try:
        toggle = Toggle.get(slug)
        ret = item in toggle.enabled_users
    except ResourceNotFound:
        ret = False
    cache.set(cache_key, ret)
    return ret


def clear_toggle_cache(slug, item, namespace=None):
    item = _namespaced_item(item, namespace)
    cache_key = get_toggle_cache_key(slug, item)
    cache.delete(cache_key)


def get_toggle_cache_key(slug, item):
    return 'toggle-{slug}:{item}'.format(slug=slug, item=item)


def _namespaced_item(item, namespace):
    return '{namespace}:{item}'.format(
        namespace=namespace, item=item
    ) if namespace is not None else item
