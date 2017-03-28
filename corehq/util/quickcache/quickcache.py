# coding=utf-8
import functools
import hashlib
import inspect
from inspect import isfunction


from corehq.util.soft_assert.api import soft_assert

from .logger import logger


class QuickCacheHelper(object):
    def __init__(self, fn, vary_on, cache, skip_arg=None):

        self.fn = fn
        self.cache = cache
        self.prefix = '{}.{}'.format(
            fn.__name__[:40] + (fn.__name__[40:] and '..'),
            self._hash(inspect.getsource(fn), 8)
        )

        arg_names = inspect.getargspec(self.fn).args
        if not isfunction(vary_on):
            vary_on = [part.split('.') for part in vary_on]
            vary_on = [(part[0], tuple(part[1:])) for part in vary_on]
            for arg, attrs in vary_on:
                if arg not in arg_names:
                    raise ValueError(
                        'We cannot vary on "{}" because the function {} has '
                        'no such argument'.format(arg, self.fn.__name__)
                    )

        self.encoding_assert = soft_assert(
            notify_admins=True,
            fail_if_debug=False,
            skip_frames=5,
        )

        self.vary_on = vary_on

        if skip_arg is None or isinstance(skip_arg, basestring) or isfunction(skip_arg):
            self.skip_arg = skip_arg
        else:
            raise ValueError("skip_arg must be None, a string, or a function")

        arg_spec = inspect.getargspec(self.fn)
        if isinstance(skip_arg, basestring) and self.skip_arg not in arg_spec.args:
            raise ValueError(
                'We cannot use "{}" as the "skip" parameter because the function {} has '
                'no such argument'.format(self.skip_arg, self.fn.__name__)
            )

        if not isfunction(self.vary_on):
            for arg, attrs in self.vary_on:
                if arg == self.skip_arg:
                    raise ValueError(
                        'You cannot use the "{}" argument as a vary on parameter and '
                        'as the "skip cache" parameter in the function: {}'.format(arg, self.fn.__name__)
                    )

    def call(self, *args, **kwargs):
        logger.debug('checking caches for {}'.format(self.fn.__name__))
        key = self.get_cache_key(*args, **kwargs)
        logger.debug(key)
        content = self.cache.get(key, default=Ellipsis)
        if content is Ellipsis:
            logger.debug('cache miss, calling {}'.format(self.fn.__name__))
            content = self.fn(*args, **kwargs)
            self.cache.set(key, content)
        return content

    def get_cached_value(self, *args, **kwargs):
        """
        :returns: The cached value or ``Ellipsis``
        """
        key = self.get_cache_key(*args, **kwargs)
        logger.debug(key)
        return self.cache.get(key, default=Ellipsis)

    def clear(self, *args, **kwargs):
        key = self.get_cache_key(*args, **kwargs)
        self.cache.delete(key)

    @staticmethod
    def _hash(value, length=32):
        return hashlib.md5(value).hexdigest()[-length:]

    def _serialize_for_key(self, value):
        if isinstance(value, basestring):
            # Unicode and string values should generate the same key since users generally
            # intend them to mean the same thing. If a use case for differentiating
            # them presents itself add a 'lenient_strings=False' option to allow
            # the user to explicitly request the different behaviour.
            if isinstance(value, unicode):
                encoded = value.encode('utf-8')
            else:
                try:
                    encoded = value.decode('utf-8').encode('utf-8')
                except UnicodeDecodeError:
                    self.encoding_assert(False, 'Non-utf8 encoded string used as cache vary on')
                    encoded = value
            return 'u' + self._hash(encoded)
        elif isinstance(value, bool):
            return 'b' + str(int(value))
        elif isinstance(value, (int, long, float)):
            return 'n' + str(value)
        elif isinstance(value, (list, tuple)):
            return 'L' + self._hash(
                ','.join(map(self._serialize_for_key, value)))
        elif isinstance(value, dict):
            return 'D' + self._hash(
                ','.join(sorted(map(self._serialize_for_key, value.items())))
            )
        elif isinstance(value, set):
            return 'S' + self._hash(
                ','.join(sorted(map(self._serialize_for_key, value))))
        elif value is None:
            return 'N'
        else:
            raise ValueError('Bad type "{}": {}'.format(type(value), value))

    def get_cache_key(self, *args, **kwargs):
        callargs = inspect.getcallargs(self.fn, *args, **kwargs)
        values = []
        if isfunction(self.vary_on):
            values = self.vary_on(*args, **kwargs)
        else:
            for arg_name, attrs in self.vary_on:
                value = callargs[arg_name]
                for attr in attrs:
                    value = getattr(value, attr)
                values.append(value)
        args_string = ','.join(self._serialize_for_key(value)
                               for value in values)
        if len(args_string) > 150:
            args_string = 'H' + self._hash(args_string)
        return 'quickcache.{}/{}'.format(self.prefix, args_string)

    def skip(self, *args, **kwargs):
        if not self.skip_arg:
            return False
        elif isinstance(self.skip_arg, basestring):
            callargs = inspect.getcallargs(self.fn, *args, **kwargs)
            return callargs[self.skip_arg]
        elif isfunction(self.skip_arg):
            return self.skip_arg(*args, **kwargs)
        else:
            assert False, "skip_arg must be None, a string, or a function " \
                          "and this should have been checked in __init__"

    def __call__(self, *args, **kwargs):
        if not self.skip(*args, **kwargs):
            return self.call(*args, **kwargs)
        else:
            content = self.fn(*args, **kwargs)
            key = self.get_cache_key(*args, **kwargs)
            self.cache.set(key, content)
            return content


def generic_quickcache(vary_on, cache, skip_arg=None, helper_class=None):
    helper_class = helper_class or QuickCacheHelper

    def decorator(fn):
        helper = helper_class(fn, vary_on=vary_on, cache=cache, skip_arg=skip_arg)

        @functools.wraps(fn)
        def inner(*args, **kwargs):
            return helper(*args, **kwargs)

        inner.clear = helper.clear
        inner.get_cache_key = helper.get_cache_key
        inner.prefix = helper.prefix
        inner.get_cached_value = helper.get_cached_value

        return inner

    return decorator
