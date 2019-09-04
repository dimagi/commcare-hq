from memoized import memoized, Memoized
import warnings

# This will be shown when anything from this file is imported.
# If you come across this after March 2018, feel free to delete this file.
warnings.warn("dimagi.utils.decorators.memoized is deprecated. "
              "Use `from memoized import memoized` instead.",
              DeprecationWarning)


__all__ = ['memoized', 'Memoized']
