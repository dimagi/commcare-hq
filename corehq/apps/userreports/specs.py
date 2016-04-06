from collections import namedtuple
from dimagi.ext.jsonobject import StringProperty
from datetime import datetime


def TypeProperty(value):
    """
    Shortcut for making a required property and restricting it to a single specified
    value. This adds additional validation that the objects are being wrapped as expected
    according to the type.
    """
    return StringProperty(required=True, choices=[value])


class FactoryContext(namedtuple('FactoryContext', ('named_expressions', 'named_filters'))):

    @staticmethod
    def empty():
        return FactoryContext({}, {})


class EvaluationContext(object):
    """
    An evaluation context. Necessary for repeats to pass both the row of the repeat as well
    as the root document and the iteration number.
    """
    def __init__(self, root_doc, iteration=0):
        self.root_doc = root_doc
        self.iteration = iteration
        self.inserted_timestamp = datetime.utcnow()
        self.cache = {}

    def get_cache_value(self, key):
        return self.cache.get(key, None)

    def set_cache_value(self, key, value):
        self.cache[key] = value
