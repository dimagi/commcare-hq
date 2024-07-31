from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from django.utils.translation import gettext
from memoized import memoized

from corehq.apps.userreports.exceptions import BadSpecError
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
class FactoryContext:
    named_expressions: dict
    _named_expressions: dict = field(init=False, repr=False)

    named_filters: dict
    _named_filters: dict = field(init=False, repr=False)

    domain: Optional[str] = None

    def __post_init__(self):
        """Initialize the stacks for tracking recursive references."""
        self._expression_stack = []
        self._filter_stack = []

    def expression_from_spec(self, spec):
        from corehq.apps.userreports.expressions.factory import ExpressionFactory
        return ExpressionFactory.from_spec(spec, self)

    def filter_from_spec(self, spec):
        from corehq.apps.userreports.filters.factory import FilterFactory
        return FilterFactory.from_spec(spec, self)

    @property
    @memoized
    def named_filters(self):
        raise Exception("Use get_named_filter instead of named_filters directly.")

    @named_filters.setter
    def named_filters(self, named_filters):
        self._named_filters = named_filters

    @property
    @memoized
    def _extra_filters(self):
        extra_filters = {}
        if self.domain and toggles.UCR_EXPRESSION_REGISTRY.enabled(self.domain):
            from corehq.apps.userreports.models import UCRExpression
            extra_filters = UCRExpression.objects.get_wrapped_filters_for_domain(self.domain, self)
        return extra_filters

    def get_named_filter(self, name):
        return self._get_named(name, self._named_filters | self._extra_filters, self._filter_stack)

    @property
    @memoized
    def named_expressions(self):
        raise Exception("Use get_named_expression instead of named_expressions directly.")

    @named_expressions.setter
    def named_expressions(self, named_expressions):
        self._named_expressions = named_expressions

    @property
    @memoized
    def _extra_expressions(self):
        extra_expressions = {}
        if self.domain and toggles.UCR_EXPRESSION_REGISTRY.enabled(self.domain):
            from corehq.apps.userreports.models import UCRExpression
            extra_expressions = UCRExpression.objects.get_wrapped_expressions_for_domain(self.domain, self)
        return extra_expressions

    def get_named_expression(self, name):
        return self._get_named(name, self._named_expressions | self._extra_expressions, self._expression_stack)

    def _get_named(self, name, named_dict, stack):
        from corehq.apps.userreports.models import LazyExpressionWrapper
        if name in stack:
            raise BadSpecError(gettext("Recursive expression reference: {name}").format(name=name))

        stack.append(name)
        try:
            expr = named_dict.get(name)
            if not expr:
                raise BadSpecError(gettext("Couldn't find named expression with name: {name}").format(name=name))
            if isinstance(expr, LazyExpressionWrapper):
                # unwrap here to force evaluation of the lazy expression and catch recursive references
                expr = expr.unwrap()
            return expr
        finally:
            stack.pop()

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
