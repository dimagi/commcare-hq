from couchdbkit.ext.django.schema import Document, StringProperty, IntegerProperty


class IndicatorDefinition(Document):
    namespace = StringProperty()
    domain = StringProperty()
    slug = StringProperty()
    version = IntegerProperty()

    def get_value(self):
        raise NotImplementedError

class FormIndicatorDefinition(IndicatorDefinition):
    xmlns = StringProperty()

class CaseIndicatorDefinition(IndicatorDefinition):
    case_type = StringProperty()