from inspect import isgenerator


class ReadOnlyObject(object):

    def __init__(self, obj):
        self._obj = obj

    def __getitem__(self, item):
        return self._obj[item]

    def __getattr__(self, item):
        value = getattr(self._obj, item)
        if isgenerator(value):
            # generator **functions** will be returned as is,
            # but if it's i.e. a @property, then you don't want to memoize
            # a generator
            value = list(value)

        setattr(self, item, value)
        return value
