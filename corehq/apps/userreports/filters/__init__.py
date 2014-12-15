from fluff.filters import Filter


class SinglePropertyValueFilter(Filter):

    def __init__(self, expression, operator, reference_value):
        self.expression = expression
        self.operator = operator
        self.reference_value = reference_value

    def filter(self, item):
        return self.operator(self.expression(item), self.reference_value)
