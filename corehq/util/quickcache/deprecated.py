import warnings
from . import quickcache
from .quickcache import QuickCache


def SkippableQuickCache(*args, **kwargs):
    warnings.warn(
        "SkippableQuickCache is deprecated. Use QuickCache with skip_arg instead.",
        DeprecationWarning
    )
    return QuickCache(*args, **kwargs)


def skippable_quickcache(*args, **kwargs):
    warnings.warn(
        "skippable_quickcache is deprecated. Use quickcache with skip_arg instead.",
        DeprecationWarning
    )
    return quickcache(*args, **kwargs)
