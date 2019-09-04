from collections import namedtuple
from datetime import datetime

from dimagi.ext.jsonobject import StringProperty


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
        self.iteration_cache = {}

    def exists_in_cache(self, key):
        return key in self.cache or key in self.iteration_cache

    def get_cache_value(self, key, default=None):
        if key in self.cache:
            return self.cache[key]

        if key in self.iteration_cache:
            return self.iteration_cache[key]

        return default

    def set_cache_value(self, key, value):
        self.cache[key] = value

    def set_iteration_cache_value(self, key, value):
        self.iteration_cache[key] = value

    def increment_iteration(self):
        self.iteration_cache = {}
        self.iteration += 1

    def reset_iteration(self):
        self.iteration_cache = {}
        self.iteration = 0
