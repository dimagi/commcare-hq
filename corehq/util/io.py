from __future__ import absolute_import
from __future__ import unicode_literals


class ClosingContextProxy(object):
    """Context manager wrapper for object with close() method

    Calls `wrapped_object.close()` on exit context.
    """

    def __init__(self, obj):
        self._obj = obj

    def __getattr__(self, name):
        return getattr(self._obj, name)

    def __iter__(self):
        return iter(self._obj)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._obj.close()
