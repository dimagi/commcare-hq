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
        assert len(self.filters) > 1

    def filter(self, item):
        return all(filter.filter(item) for filter in self.filters)


class ORFilter(Filter):
    """
    Lets you construct OR operations on filters.
    """
    def __init__(self, filters):
        self.filters = filters
        assert len(self.filters) > 1

    def filter(self, item):
        return any(filter.filter(item) for filter in self.filters)

