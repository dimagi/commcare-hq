from couchdbkit.ext.django.schema import Document, SchemaListProperty, DictProperty, StringProperty, DocumentSchema, Property

class SelectChoice(DocumentSchema):
    label = DictProperty()
    stringValue = StringProperty()
    value = Property()

class CasePropertySpec(DocumentSchema):
    key = StringProperty()
    label = DictProperty()
    type = StringProperty(choices=['string', 'select', 'date', 'group'], default='string')
    choices = SchemaListProperty(SelectChoice)

class CaseSpec(Document):
    case_type = StringProperty()
    propertySpecs = SchemaListProperty(CasePropertySpec)
