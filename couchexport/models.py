from couchdbkit.ext.django.schema import Document, IntegerProperty, DictProperty


class ExportSchema(Document):
    """
    An export schema that can store intermittent contents of the export so
    that the entire doc list doesn't have to be used to generate the export
    """
    seq = IntegerProperty()
    schema = DictProperty()
    