from .quickcache import get_quickcache
from .django_quickcache import get_django_quickcache
from .quickcache_helper import QuickCacheHelper


__all__ = [
    'get_django_quickcache',
    'get_quickcache',
    'QuickCacheHelper',
]
