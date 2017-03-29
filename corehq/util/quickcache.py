from __future__ import absolute_import
import warnings
from quickcache.django_quickcache import django_quickcache


def quickcache(vary_on, skip_arg=None, timeout=5 * 60, memoize_timeout=10):
    return django_quickcache(vary_on, skip_arg=skip_arg, timeout=timeout, memoize_timeout=memoize_timeout)


def skippable_quickcache(*args, **kwargs):
    warnings.warn(
        "skippable_quickcache is deprecated. Use quickcache with skip_arg instead.",
        DeprecationWarning
    )
    return quickcache(*args, **kwargs)


__all__ = ['quickcache', 'skippable_quickcache']
