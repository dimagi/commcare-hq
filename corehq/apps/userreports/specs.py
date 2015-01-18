from jsonobject import StringProperty, DictProperty, JsonObject


def TypeProperty(value):
    """
    Shortcut for making a required property and restricting it to a single specified
    value. This adds additional validation that the objects are being wrapped as expected
    according to the type.
    """
    return StringProperty(required=True, choices=[value])


class EvaluationContext(object):
    """
    An evaluation context. Necessary for repeats to pass both the row of the repeat as well
    as the base document.
    """
    def __init__(self, base_doc):
        self.base_doc = base_doc
