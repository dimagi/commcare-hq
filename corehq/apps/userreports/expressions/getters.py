from decimal import Decimal, InvalidOperation


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
        if not isinstance(item, dict):
            return None
        try:
            return recursive_lookup(item, self.property_path)
        except (KeyError, TypeError):
            # key errors are missing keys
            # type errors are valid keys that return the wrong type
            return None


def recursive_lookup(dict_object, keys):
    """
    Given a dict object and list of keys, nest into those keys.
    Raises KeyError if the path isn't found.
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
    return item or None


def transform_datetime(item):
    return item or None


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
        return unicode(item)
    except (ValueError, TypeError):
        return None


def transform_from_datatype(datatype):
    """
    Given a datatype, return a transform for that type.
    """
    identity = lambda x: x
    return {
        'date': transform_date,
        'datetime': transform_datetime,
        'decimal': transform_decimal,
        'integer': transform_int,
        'string': transform_unicode,
    }.get(datatype) or identity


def getter_from_property_reference(spec):
    if spec.property_name:
        assert not spec.property_path, \
            'indicator {} has both a name and path specified! you must only pick one.'.format(spec.property_name)
        return DictGetter(property_name=spec.property_name)
    else:
        assert spec.property_path, spec.property_name
        return NestedDictGetter(property_path=spec.property_path)
