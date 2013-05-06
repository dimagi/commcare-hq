# See http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
import functools
from inspect import getargspec, ismethod, isfunction
import sys

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
    {(Person('Danny', 'Roberts'),): 'Danny Roberts'}
    >>> p.full_name
    'Danny Roberts'
    >>> Person.get_full_name.get_cache(p)
    {(Person('Danny', 'Roberts'),): 'Danny Roberts'}
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
        key = self.get_args_tuple(*args, **kwargs)
        if self.is_method:
            obj = args[0]
        else:
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

try:
    from inspect import getcallargs
except ImportError:
    # copied from python 2.7 inspect module for compatibility with 2.6
    def getcallargs(func, *positional, **named):
        """Get the mapping of arguments to values.

        A dict is returned, with keys the function argument names (including the
        names of the * and ** arguments, if any), and values the respective bound
        values from 'positional' and 'named'."""
        args, varargs, varkw, defaults = getargspec(func)
        f_name = func.__name__
        arg2value = {}

        # The following closures are basically because of tuple parameter unpacking.
        assigned_tuple_params = []
        def assign(arg, value):
            if isinstance(arg, str):
                arg2value[arg] = value
            else:
                assigned_tuple_params.append(arg)
                value = iter(value)
                for i, subarg in enumerate(arg):
                    try:
                        subvalue = next(value)
                    except StopIteration:
                        raise ValueError('need more than %d %s to unpack' %
                                         (i, 'values' if i > 1 else 'value'))
                    assign(subarg,subvalue)
                try:
                    next(value)
                except StopIteration:
                    pass
                else:
                    raise ValueError('too many values to unpack')
        def is_assigned(arg):
            if isinstance(arg,str):
                return arg in arg2value
            return arg in assigned_tuple_params
        if ismethod(func) and func.im_self is not None:
            # implicit 'self' (or 'cls' for classmethods) argument
            positional = (func.im_self,) + positional
        num_pos = len(positional)
        num_total = num_pos + len(named)
        num_args = len(args)
        num_defaults = len(defaults) if defaults else 0
        for arg, value in zip(args, positional):
            assign(arg, value)
        if varargs:
            if num_pos > num_args:
                assign(varargs, positional[-(num_pos-num_args):])
            else:
                assign(varargs, ())
        elif 0 < num_args < num_pos:
            raise TypeError('%s() takes %s %d %s (%d given)' % (
                f_name, 'at most' if defaults else 'exactly', num_args,
                'arguments' if num_args > 1 else 'argument', num_total))
        elif num_args == 0 and num_total:
            if varkw:
                if num_pos:
                    # XXX: We should use num_pos, but Python also uses num_total:
                    raise TypeError('%s() takes exactly 0 arguments '
                                    '(%d given)' % (f_name, num_total))
            else:
                raise TypeError('%s() takes no arguments (%d given)' %
                                (f_name, num_total))
        for arg in args:
            if isinstance(arg, str) and arg in named:
                if is_assigned(arg):
                    raise TypeError("%s() got multiple values for keyword "
                                    "argument '%s'" % (f_name, arg))
                else:
                    assign(arg, named.pop(arg))
        if defaults:    # fill in any missing values with the defaults
            for arg, value in zip(args[-num_defaults:], defaults):
                if not is_assigned(arg):
                    assign(arg, value)
        if varkw:
            assign(varkw, named)
        elif named:
            unexpected = next(iter(named))
            if isinstance(unexpected, unicode):
                unexpected = unexpected.encode(sys.getdefaultencoding(), 'replace')
            raise TypeError("%s() got an unexpected keyword argument '%s'" %
                            (f_name, unexpected))
        unassigned = num_args - len([arg for arg in args if is_assigned(arg)])
        if unassigned:
            num_required = num_args - num_defaults
            raise TypeError('%s() takes %s %d %s (%d given)' % (
                f_name, 'at least' if defaults else 'exactly', num_required,
                'arguments' if num_required > 1 else 'argument', num_total))
        return arg2value
