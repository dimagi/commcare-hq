from __future__ import absolute_import
import warnings
from quickcache.django_quickcache import get_django_quickcache


from corehq.util.soft_assert import soft_assert

quickcache_soft_assert = soft_assert(
    notify_admins=True,
    fail_if_debug=False,
    skip_frames=5,
)

quickcache = get_django_quickcache(timeout=5 * 60, memoize_timeout=0,
                                   assert_function=quickcache_soft_assert)


def skippable_quickcache(*args, **kwargs):
    warnings.warn(
        "skippable_quickcache is deprecated. Use quickcache with skip_arg instead.",
        DeprecationWarning
    )
    return quickcache(*args, **kwargs)


__all__ = ['quickcache', 'skippable_quickcache']
