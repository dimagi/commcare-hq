from couchdbkit.ext.django.schema import *

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

class CommtrackActionConfig(DocumentSchema):
    keyword = StringProperty()
    multiaction_keyword = StringProperty() # defaults to single-action keyword
    caption = StringProperty()

    def _keyword(self, multi):
        if multi:
            return self.multiaction_keyword or self.keyword
        else:
            return self.keyword

class CommtrackConfig(Document):
    domain = StringProperty()

    # supported stock actions for this commtrack domain
    #   action type (see ACTION_TYPES) => action config
    actions = SchemaDictProperty(CommtrackActionConfig)

    multiaction_enabled = BooleanProperty()
    multiaction_keyword = StringProperty() # if None, will attempt to parse
      # all messages as multi-action
    multiaction_delimiter = StringProperty() # default '.'

    @classmethod
    def for_domain(cls, domain):
        result = cls.view("commtrack/domain_config",
                          key=[domain],
                          include_docs=True).one()
        return result

    def keywords(self, multi=False):
        return dict((action_config._keyword(multi), action_type) for action_type, action_config in self.actions.iteritems())
