

class TransformedGetter(object):
    """
    Getter that takes in another getter and a transform function.

    Returns the result of calling the transform function on result of the getter.
    """
    def __init__(self, getter, transform=None):
        self.getter = getter
        self.transform = transform

    def __call__(self, item):
        extracted = self.getter(item)
        if self.transform:
            return self.transform(extracted)
        return extracted


class DictGetter(object):

    def __init__(self, property_name):
        self.property_name = property_name

    def __call__(self, item):
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

    def __call__(self, item):
        if not isinstance(item, dict):
            return None
        try:
            return recursive_lookup(item, self.property_path)
        except KeyError:
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
