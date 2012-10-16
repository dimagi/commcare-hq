from django.forms import fields

class CSVListField(fields.CharField):
    """
        When you want a CharField that returns a list.
    """

    def to_python(self, value):
        if isinstance(value, list):
            return ", ".join(value)
        return [v.strip() for v in value.split(',')]

    def prepare_value(self, value):
        if isinstance(value, list):
            return ", ".join(value)
        return value