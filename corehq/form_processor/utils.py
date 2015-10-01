import functools
import types
import collections


class ToFromGeneric(object):
    def to_generic(self):
        raise NotImplementedError()

    @classmethod
    def from_generic(cls, obj_dict, **kwargs):
        raise NotImplementedError()


def to_generic(fn):
    """
    Helper decorator to convert from a DB type to a generic type by calling 'to_generic'
    on the db type. e.g. FormData to XFormInstance
    """
    def _wrap(obj):
        if hasattr(obj, 'to_generic'):
            return obj.to_generic()
        else:
            return obj

    @functools.wraps(fn)
    def _inner(*args, **kwargs):
        obj = fn(*args, **kwargs)
        try:
            return obj.to_generic()
        except AttributeError:
            pass
        if isinstance(obj, (list, tuple)):
            return [_wrap(ob) for ob in obj]
        elif isinstance(obj, (types.GeneratorType, collections.Iterable)):
            return (_wrap(ob) for ob in obj)
        else:
            return _wrap(obj)

    return _inner
