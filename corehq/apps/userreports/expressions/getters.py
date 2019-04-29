from __future__ import absolute_import
from __future__ import unicode_literals

import functools
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from six import string_types

from corehq.util import eval_lazy
from corehq.util.dates import iso_string_to_date, iso_string_to_datetime
import six


def evaluate_lazy_args(func, *args):
    args = [eval_lazy(arg) for arg in args]
    return func(*args)


class TransformedGetter(object):
    """
    Getter that takes in another getter and a transform function.

    Returns the result of calling the transform function on result of the getter.
    """

    def __init__(self, getter, transform=None):
        self.getter = getter
        self.transform = transform

    def __call__(self, item, context=None):
        extracted = self.getter(item, context)
        if self.transform:
            return self.transform(extracted)
        return extracted


class DictGetter(object):

    def __init__(self, property_name):
        self.property_name = property_name

    def __call__(self, item, context=None):
        if not isinstance(item, dict):
            return None
        try:
            return item[self.property_name]
        except KeyError:
            return None


class NestedDictGetter(object):
    """
    Gets a property from a series of nested dicts. Takes in a fully qualified
    path to the value in question in the form of a list. Returns None if the path
    does not exist in the dict.
    """

    def __init__(self, property_path):
        self.property_path = property_path

    def __call__(self, item, context=None):
        return safe_recursive_lookup(item, self.property_path)


def safe_recursive_lookup(item, path):
    """
    Like recursive_lookup but returns `None` on any expected errors.
    """
    if not isinstance(item, dict):
        return None
    try:
        return recursive_lookup(item, path)
    except (KeyError, TypeError, ValueError):
        # key errors are missing keys
        # type errors are valid keys that return the wrong type
        # value errors are empty keys
        return None


def recursive_lookup(dict_object, keys):
    """
    Given a dict object and list of keys, nest into those keys.

    :raises KeyError if the path isn't found.
    :raises TypeError if dict_object is not a dict
    :raises ValueError if keys is empty

    >>> recursive_lookup({'foo': 1}, ['foo'])
    1
    >>> recursive_lookup({'foo': {'bar': 1}}, ['foo'])
    {'bar': 1}
    >>> recursive_lookup({'foo': {'bar': 1}}, ['foo', 'bar'])
    1
    """
    if not keys or not isinstance(keys, list):
        raise ValueError('Keys must be a non-empty list!')

    if len(keys) == 1:
        return dict_object[keys[0]]
    else:
        return recursive_lookup(dict_object[keys[0]], keys[1:])


def transform_date(item):
    # postgres crashes on empty strings, but is happy to take null dates
    if item:
        if isinstance(item, string_types):
            try:
                return iso_string_to_date(item)
            except ValueError:
                try:
                    return iso_string_to_datetime(item, strict=True).date()
                except ValueError:
                    return None
        elif isinstance(item, datetime):
            return item.date()
        elif isinstance(item, date):
            return item
    return None


def transform_datetime(item):
    if item:
        if isinstance(item, string_types):
            try:
                return iso_string_to_datetime(item, strict=True)
            except ValueError:
                try:
                    parsed_item = iso_string_to_date(item)
                    return datetime.combine(parsed_item, time(0, 0, 0))
                except ValueError:
                    pass
        elif isinstance(item, datetime):
            return item
        elif isinstance(item, date):
            return datetime.combine(item, time(0, 0, 0))

    return None


def transform_int(item):
    try:
        return int(item)
    except (ValueError, TypeError):
        try:
            return int(float(item))
        except (ValueError, TypeError):
            return None


def transform_decimal(item):
    try:
        return Decimal(item)
    except (ValueError, TypeError, InvalidOperation):
        return None


def transform_unicode(item):
    if item is None:
        return None
    try:
        return six.text_type(item)
    except (ValueError, TypeError):
        return None


def transform_array(item):
    if isinstance(item, list):
        return item
    return [item]


def transform_from_datatype(datatype):
    """
    Given a datatype, return a transform for that type.
    """
    identity = lambda x: x
    transform = {
        'date': transform_date,
        'datetime': transform_datetime,
        'decimal': transform_decimal,
        'integer': transform_int,
        'small_integer': transform_int,
        'string': transform_unicode,
        'array': transform_array,
    }.get(datatype) or identity
    return functools.partial(evaluate_lazy_args, transform)


def getter_from_property_reference(spec):
    if spec.property_name:
        assert not spec.property_path, \
            'indicator {} has both a name and path specified! you must only pick one.'.format(spec.property_name)
        return functools.partial(evaluate_lazy_args, DictGetter(property_name=spec.property_name))
    else:
        assert spec.property_path, spec.property_name
        return functools.partial(evaluate_lazy_args, NestedDictGetter(property_path=spec.property_path))
