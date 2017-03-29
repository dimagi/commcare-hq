from __future__ import absolute_import
import warnings
from quickcache.django_quickcache import get_django_quickcache


quickcache = get_django_quickcache(timeout=5 * 60, memoize_timeout=10)


def skippable_quickcache(*args, **kwargs):
    warnings.warn(
        "skippable_quickcache is deprecated. Use quickcache with skip_arg instead.",
        DeprecationWarning
    )
    return quickcache(*args, **kwargs)


__all__ = ['quickcache', 'skippable_quickcache']
