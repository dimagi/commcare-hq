from couchdbkit.ext.django.schema import Document, StringProperty,\
    BooleanProperty, DateTimeProperty, IntegerProperty, DocumentSchema, SchemaProperty, DictProperty, ListProperty

class Product(Document):
    domain = StringProperty()
    name = StringProperty()
    unit = StringProperty()
    code = StringProperty()
    description = StringProperty()
    category = StringProperty()

    @classmethod
    def get_by_code(cls, domain, code):
        result = cls.view("commtrack/product_by_code",
                          key=[domain, code],
                          include_docs=True).first()
        return result


