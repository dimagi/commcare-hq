from .quickcache import (
    generic_quickcache,
    QuickCacheHelper,
)
from .django_quickcache import quickcache

from .deprecated import SkippableQuickCache, skippable_quickcache


__all__ = [
    'generic_quickcache',
    'quickcache',
    'skippable_quickcache',
    'QuickCacheHelper',
    'SkippableQuickCache',
]
