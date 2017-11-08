# See http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
from __future__ import absolute_import
import functools
from inspect import getargspec, getcallargs, isfunction

def memoized(fn):
    m = Memoized(fn)
    try:
        @functools.wraps(fn)
        def _inner(*args, **kwargs):
            return m(*args, **kwargs)
    except TypeError:
        _inner = m
    _inner.get_cache = m.get_cache
    _inner.reset_cache = m.reset_cache
    return _inner


class Memoized(object):
    """Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).
    >>> from dimagi.utils.decorators.memoized import memoized
    >>> @memoized
    ... def f(n=0):
    ...     return n**2
    >>> f()
    0
    >>> f.get_cache()
    {(0,): 0}
    >>> f(0)
    0
    >>> f.get_cache()
    {(0,): 0}
    >>> f(2)
    4
    >>> sorted(f.get_cache().items())
    [((0,), 0), ((2,), 4)]
    >>> @memoized
    ... class Person(object):
    ...     def __init__(self, first_name, last_name):
    ...         self.first_name = first_name
    ...         self.last_name = last_name
    ...     @property
    ...     @memoized
    ...     def full_name(self):
    ...         print "Computing full name"
    ...         return "%s %s" % (self.first_name, self.last_name)
    ...     @memoized
    ...     def get_full_name(self):
    ...         print "Computing full name"
    ...         return "%s %s" % (self.first_name, self.last_name)
    ...     def __repr__(self):
    ...         return "%s(%r, %r)" % (self.__class__.__name__, self.first_name, self.last_name)
    ...     @memoized
    ...     def complicated_method(self, a, b=10, *args, **kwargs):
    ...         print "Calling complicated method"
    ...         return a, b, args, kwargs
    >>> p = Person("Danny", "Roberts")
    >>> p.get_full_name()
    Computing full name
    'Danny Roberts'
    >>> p.get_full_name()
    'Danny Roberts'
    >>> p.full_name
    Computing full name
    'Danny Roberts'
    >>> Person("Danny", "Roberts")._full_name_cache
    {(): 'Danny Roberts'}
    >>> p.full_name
    'Danny Roberts'
    >>> Person.get_full_name.get_cache(p)
    {(): 'Danny Roberts'}
    >>> p.complicated_method(5)
    Calling complicated method
    (5, 10, (), {})
    >>> p.complicated_method(5)
    (5, 10, (), {})
    >>> p.complicated_method(1, 2, 3, 4, 5, foo='bar')
    Calling complicated method
    (1, 2, (3, 4, 5), {'foo': 'bar'})
    >>> q = Person("Joe", "Schmoe")
    >>> q.get_full_name()
    Computing full name
    'Joe Schmoe'
    """
    def __init__(self, func):

        if isfunction(func):
            self.func = func
        else:
            def wrapped(*args, **kwargs):
                return func(*args, **kwargs)
            self.func = wrapped
        self.argspec = getargspec(self.func)
        if self.argspec.args and self.argspec.args[0] == 'self':
            self.is_method = True
        else:
            self.is_method = False
            self._cache = {}

    def get_cache(self, obj=None):
        if self.is_method:
            cache_attr = '_%s_cache' % self.func.__name__
            try:
                cache = getattr(obj, cache_attr)
            except (KeyError, AttributeError):
                cache = {}
                setattr(obj, cache_attr, cache)
            return cache
        else:
            return self._cache

    def reset_cache(self, obj=None):
        self.get_cache(obj).clear()

    def __call__(self, *args, **kwargs):
        if self.is_method:
            key = self.get_args_tuple(*args, **kwargs)[1:]
            obj = args[0]
        else:
            key = self.get_args_tuple(*args, **kwargs)
            obj = None
        cache = self.get_cache(obj)
        try:
            return cache[key]
        except KeyError:
            value = self.func( *args, **kwargs)
            cache[key] = value
            return value

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def get_args_tuple(self, *args, **kwargs):
        """
        Take a function and the arguments you'd call it with
        and return a tuple
        """
        arg_names, args_name, kwargs_name, ___ = self.argspec
        values = getcallargs(self.func, *args, **kwargs)
        in_order = [values[arg_name] for arg_name in arg_names]
        if args_name:
            in_order.append(values[args_name])
        if kwargs_name:
            in_order.append(tuple(sorted(values[kwargs_name].items())))
        return tuple(in_order)
