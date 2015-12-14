# NOTE: this module is heavily copied from fluff, but with some extensions
# The largest change is the addition of the evaluation context to every filter


class Filter(object):
    """
    Base filter class
    """

    def __call__(self, item, context=None):
        return True


class NOTFilter(Filter):
    def __init__(self, filter):
        self._filter = filter

    def __call__(self, item, context=None):
        return not self._filter(item)


class ANDFilter(Filter):
    """
    Lets you construct AND operations on filters.
    """
    def __init__(self, filters):
        self.filters = filters
        assert len(self.filters) > 0

    def __call__(self, item, context=None):
        return all(filter(item, context) for filter in self.filters)


class ORFilter(Filter):
    """
    Lets you construct OR operations on filters.
    """
    def __init__(self, filters):
        self.filters = filters
        assert len(self.filters) > 0

    def __call__(self, item, context=None):
        return any(filter(item, context) for filter in self.filters)


class CustomFilter(Filter):
    """
    This filter allows you to pass in a function reference to use as the filter

    e.g. CustomFilter(lambda f, context: f['gender'] in ['male', 'female'])
    """
    def __init__(self, filter):
        self._filter = filter

    def __call__(self, item, context=None):
        return self._filter(item, context)


class SinglePropertyValueFilter(Filter):

    def __init__(self, expression, operator, reference_expression):
        self.expression = expression
        self.operator = operator
        self.reference_expression = reference_expression

    def __call__(self, item, context=None):
        return self.operator(self.expression(item, context), self.reference_expression(item, context))
