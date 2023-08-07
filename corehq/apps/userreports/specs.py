from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from memoized import memoized

from dimagi.ext.jsonobject import StringProperty

from corehq import toggles


def TypeProperty(value):
    """
    Shortcut for making a required property and restricting it to a single specified
    value. This adds additional validation that the objects are being wrapped as expected
    according to the type.
    """
    return StringProperty(required=True, choices=[value])


@dataclass
class FactoryContext():
    named_expressions: dict
    _named_expressions: dict = field(init=False, repr=False)

    named_filters: dict
    _named_filters: dict = field(init=False, repr=False)

    domain: Optional[str] = None

    def expression_from_spec(self, spec):
        from corehq.apps.userreports.expressions.factory import ExpressionFactory
        return ExpressionFactory.from_spec(spec, self)

    def filter_from_spec(self, spec):
        from corehq.apps.userreports.filters.factory import FilterFactory
        return FilterFactory.from_spec(spec, self)

    @property
    @memoized
    def named_filters(self):
        extra_filters = {}
        if self.domain and toggles.UCR_EXPRESSION_REGISTRY.enabled(self.domain):
            from corehq.apps.userreports.models import UCRExpression
            extra_filters = UCRExpression.objects.get_wrapped_filters_for_domain(self.domain, self)
        return extra_filters | self._named_filters

    @named_filters.setter
    def named_filters(self, named_filters):
        self._named_filters = named_filters

    @property
    @memoized
    def named_expressions(self):
        extra_expressions = {}
        if self.domain and toggles.UCR_EXPRESSION_REGISTRY.enabled(self.domain):
            from corehq.apps.userreports.models import UCRExpression
            extra_expressions = UCRExpression.objects.get_wrapped_expressions_for_domain(self.domain, self)
        return extra_expressions | self._named_expressions

    @named_expressions.setter
    def named_expressions(self, named_expressions):
        self._named_expressions = named_expressions

    @staticmethod
    def empty(domain=None):
        return FactoryContext({}, {}, domain)


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

    @staticmethod
    def empty():
        return EvaluationContext({})
