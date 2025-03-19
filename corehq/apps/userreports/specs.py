import weakref
from contextlib import contextmanager
from datetime import datetime

from django.utils.translation import gettext
from memoized import memoized

from corehq import toggles
from corehq.apps.userreports.exceptions import BadSpecError
from dimagi.ext.jsonobject import StringProperty


def TypeProperty(value):
    """
    Shortcut for making a required property and restricting it to a single specified
    value. This adds additional validation that the objects are being wrapped as expected
    according to the type.
    """
    return StringProperty(required=True, choices=[value])


class BaseContainer:
    """Class used to manage access to named filters and expressions and
    check for circular references.
    """
    def __init__(self, factory_context, expressions, domain=None):
        self.factory_context = weakref.proxy(factory_context)
        self.expressions = expressions
        self.domain = domain
        self.stack = set()

    def replace(self, expressions):
        self.expressions = expressions

    def __getitem__(self, item):
        with self._search_scope(item):
            from corehq.apps.userreports.models import LazyExpressionWrapper
            all_expressions = self._get_db_expressions() | self.expressions
            expr = all_expressions.get(item)
            if not expr:
                raise KeyError(item)
            if isinstance(expr, LazyExpressionWrapper):
                # load here to force evaluation of the lazy expression and catch recursive references
                expr = expr.wrapped_expression
            return expr

    @contextmanager
    def _search_scope(self, name):
        """Return a context manager that will raise an error if the name is already in the stack."""
        if name in self.stack:
            raise BadSpecError(gettext("Recursive expression reference: {name}").format(name=name))

        self.stack.add(name)
        try:
            yield self
        finally:
            self.stack.remove(name)

    @memoized
    def _get_db_expressions(self):
        if self.domain and toggles.UCR_EXPRESSION_REGISTRY.enabled(self.domain):
            return self._load_db_expressions()
        return {}

    def _load_db_expressions(self):
        raise NotImplementedError()


class FilterContainer(BaseContainer):
    def _load_db_expressions(self):
        from corehq.apps.userreports.models import UCRExpression
        return UCRExpression.objects.get_wrapped_filters_for_domain(self.domain, self.factory_context)


class ExpressionContainer(BaseContainer):
    def _load_db_expressions(self):
        from corehq.apps.userreports.models import UCRExpression
        return UCRExpression.objects.get_wrapped_expressions_for_domain(self.domain, self.factory_context)


class FactoryContext:
    def __init__(self, named_expressions, named_filters, domain=None):
        self.named_expressions = ExpressionContainer(self, named_expressions, domain)
        self.named_filters = FilterContainer(self, named_filters, domain)
        self.domain = domain

    def expression_from_spec(self, spec):
        from corehq.apps.userreports.expressions.factory import ExpressionFactory
        return ExpressionFactory.from_spec(spec, self)

    def filter_from_spec(self, spec):
        from corehq.apps.userreports.filters.factory import FilterFactory
        return FilterFactory.from_spec(spec, self)

    def get_named_filter(self, name):
        try:
            return self.named_filters[name]
        except KeyError as e:
            raise BadSpecError(gettext("Named filter not found: {name}").format(name=name)) from e

    def get_named_expression(self, name):
        try:
            return self.named_expressions[name]
        except KeyError as e:
            raise BadSpecError(gettext("Named expression not found: {name}").format(name=name)) from e

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
