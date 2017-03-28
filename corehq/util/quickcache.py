from __future__ import absolute_import
import warnings
from quickcache import quickcache


def skippable_quickcache(*args, **kwargs):
    warnings.warn(
        "skippable_quickcache is deprecated. Use quickcache with skip_arg instead.",
        DeprecationWarning
    )
    return quickcache(*args, **kwargs)


__all__ = ['quickcache', 'skippable_quickcache']
