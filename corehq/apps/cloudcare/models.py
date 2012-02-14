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
    name = StringProperty()
    domain = StringProperty()
    case_type = StringProperty()
    propertySpecs = SchemaListProperty(CasePropertySpec)

    @classmethod
    def get_suggested(cls, domain, case_type=None):
        key = [domain]
        if case_type:
            key.append(case_type)
        return cls.view('cloudcare/case_specs_by_domain_case_type',
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key + [{}],
        )
