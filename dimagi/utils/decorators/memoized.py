# See http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
import functools

class memoized(object):
    """Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).
    """
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args):
        return self.call(None, self.cache, *args)

    def call(self, obj, cache, *args):
        try:
            return cache[args]
        except KeyError:
            if obj:
                value = self.func(obj, *args)
            else:
                value = self.func(*args)
            cache[args] = value
            return value

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        cache_attr = '_%s_cache' % self.func.__name__
        try:
            cache = getattr(obj, cache_attr)
        except AttributeError:
            cache = {}
            setattr(obj, cache_attr, cache)
        return functools.partial(self.call, obj, cache)