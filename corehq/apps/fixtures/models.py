from couchdbkit.ext.django.schema import DocumentSchema, Document, SchemaProperty, SchemaListProperty, DictProperty

class FixtureNode(DocumentSchema):
    children = SchemaListProperty(FixtureNode)
    attributes = DictProperty()

class Fixture(Document):
    root = SchemaProperty(FixtureNode)