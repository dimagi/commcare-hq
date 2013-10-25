from couchdbkit import ResourceNotFound
from django.core.cache import cache
from .models import Toggle


def toggle_enabled(slug, username, check_cache=True):
    """
    Given a toggle and a username, whether the toggle is enabled for that user
    """
    cache_key = 'toggle-{slug}:{username}'
    if check_cache:
        from_cache = cache.get(cache_key)
        if from_cache is not None:
            return from_cache
    try:
        toggle = Toggle.get(slug)
        ret = username in toggle.enabled_users
    except ResourceNotFound:
        ret = False
    cache.set(cache_key, ret)
    return ret
