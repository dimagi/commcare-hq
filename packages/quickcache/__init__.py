from .quickcache import QuickCacheHelper, get_quickcache
from .django_quickcache import get_django_quickcache


__all__ = [
    'get_django_quickcache',
    'get_quickcache',
    'QuickCacheHelper',
]
