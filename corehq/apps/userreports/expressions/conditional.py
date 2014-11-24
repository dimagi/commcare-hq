


class ConditionalExpression(object):

    def __init__(self, test_function, expression_if_true, expression_if_false):
        self.test_function = test_function
        self.expression_if_true = expression_if_true
        self.expression_if_false = expression_if_false

    def __call__(self, item):
        if self.test_function.filter(item):
            return self.expression_if_true(item)
        else:
            return self.expression_if_false(item)
