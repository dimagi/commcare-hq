from fluff.filters import Filter


class ConfigurableFilter(Filter):
    # this currently has the exact same API as fluff.filters.Filter
    # but adds a function (from_spec)
    def filter(self, item):
        raise NotImplementedError()

    @classmethod
    def from_spec(cls, spec):
        raise NotImplementedError()


class SinglePropertyValueFilter(ConfigurableFilter):

    def __init__(self, getter, operator, reference_value):
        self.getter = getter
        self.operator = operator
        self.reference_value = reference_value

    def filter(self, item):
        return self.operator(self.getter(item), self.reference_value)
