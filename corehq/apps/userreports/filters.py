from fluff.filters import Filter


class SinglePropertyValueFilter(Filter):

    def __init__(self, getter, operator, reference_value):
        self.getter = getter
        self.operator = operator
        self.reference_value = reference_value

    def filter(self, item):
        return self.operator(self.getter(item), self.reference_value)
