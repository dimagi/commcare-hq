from couchdbkit.ext.django.schema import Document, StringProperty,\
    BooleanProperty, DateTimeProperty, IntegerProperty, DocumentSchema, SchemaProperty, DictProperty, ListProperty

# these are the allowable stock transaction types, in the order
# they are processed
ACTION_TYPES = [
    # indicates the product has been stocked out for N days
    # prior to the reporting date
    'stockedoutfor',

    # indicates the stock on hand at the start of the reporting
    # visit, prior to any transactions taking place during that
    # visit
    'prevstockonhand',

    # additions to stock
    'receipts',

    # subtractions from stock
    'consumption',

    # indicates the current stock on hand as of the end of
    # the reporting visit
    'stockonhand',

    # immediately indicates that product is stocked out right now
    'stockout',
]

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

