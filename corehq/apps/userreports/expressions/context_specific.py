

class BaseDocExpression(object):
    """
    Expression that calls another expression on context.base_doc.
    Unlike other expressions, it ignores the passed in item completely
    """
    def __init__(self, expression):
        self.expression = expression

    def __call__(self, item, context=None):
        if context is None:
            return None
        return self.expression(context.base_doc, context)
