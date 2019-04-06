# NOTE: this module is heavily copied from fluff, but with some extensions
# The largest change is the addition of the evaluation context to every filter


from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.userreports.operators import OPERATOR_DISPLAY
from corehq.apps.userreports.util import add_tabbed_text
from corehq.apps.userreports.const import NAMED_FILTER_PREFIX


class Filter(object):
    """
    Base filter class
    """

    def __call__(self, item, context=None):
        return True

    def __str__(self):
        raise NotImplementedError()


class NOTFilter(Filter):

    def __init__(self, filter):
        self._filter = filter

    def __call__(self, item, context=None):
        return not self._filter(item, context)

    def __str__(self):
        return "not({})".format(str(self._filter))


class ANDFilter(Filter):
    """
    Lets you construct AND operations on filters.
    """

    def __init__(self, filters):
        self.filters = filters
        assert len(self.filters) > 0

    def __call__(self, item, context=None):
        return all(_filter(item, context) for _filter in self.filters)

    def __str__(self):
        return "and(\n{}\n)".format(
            add_tabbed_text("\n,\n".join([str(f) for f in self.filters])))


class ORFilter(Filter):
    """
    Lets you construct OR operations on filters.
    """

    def __init__(self, filters):
        self.filters = filters
        assert len(self.filters) > 0

    def __call__(self, item, context=None):
        return any(_filter(item, context) for _filter in self.filters)

    def __str__(self):
        return "or(\n{}\n)".format(
            add_tabbed_text("\n,\n".join([str(f) for f in self.filters])))


class CustomFilter(Filter):
    """
    This filter allows you to pass in a function reference to use as the filter

    e.g. CustomFilter(lambda f, context: f['gender'] in ['male', 'female'])
    """

    def __init__(self, filter):
        self._filter = filter

    def __call__(self, item, context=None):
        return self._filter(item, context)

    def __str__(self):
        return str(self._filter)


class SinglePropertyValueFilter(Filter):

    def __init__(self, expression, operator, reference_expression):
        self.expression = expression
        self.operator = operator
        self.reference_expression = reference_expression

    def __call__(self, item, context=None):
        return self.operator(self.expression(item, context), self.reference_expression(item, context))

    def __str__(self):
        return "{} {} '{}'".format(str(self.expression),
                                   OPERATOR_DISPLAY[self.operator.__name__],
                                   str(self.reference_expression))


class NamedFilter(Filter):
    def __init__(self, filter_name, filter):
        self.filter_name = filter_name
        self.filter = filter

    def __call__(self, item, context=None):
        return self.filter(item, context)

    def __str__(self):
        return "{}:{}".format(NAMED_FILTER_PREFIX, self.filter_name)
