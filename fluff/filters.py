
def filter_by(fn):
    fn._fluff_filter = True
    return fn


class Filter(object):
    """
    Base filter class
    """

    def filter(self, item):
        return True


class NOTFilter(Filter):
    def __init__(self, filter):
        self._filter = filter

    def filter(self, item):
        return not self._filter.filter(item)


class ANDFilter(Filter):
    """
    Lets you construct AND operations on filters.
    """
    def __init__(self, filters):
        self.filters = filters
        assert len(self.filters) > 0

    def filter(self, item):
        return all(filter.filter(item) for filter in self.filters)


class ORFilter(Filter):
    """
    Lets you construct OR operations on filters.
    """
    def __init__(self, filters):
        self.filters = filters
        assert len(self.filters) > 0

    def filter(self, item):
        return any(filter.filter(item) for filter in self.filters)


class CustomFilter(Filter):
    """
    This filter allows you to pass in a function reference to use as the filter

    e.g. CustomFilter(lambda f: f.gender in ['male', 'female'])
    """
    def __init__(self, filter):
        self._filter = filter

    def filter(self, item):
        return self._filter(item)
