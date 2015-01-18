

class ConditionalExpression(object):

    def __init__(self, test_function, expression_if_true, expression_if_false):
        self.test_function = test_function
        self.expression_if_true = expression_if_true
        self.expression_if_false = expression_if_false

    def __call__(self, item, context=None):
        if self.test_function.filter(item, context):
            return self.expression_if_true(item, context)
        else:
            return self.expression_if_false(item, context)
