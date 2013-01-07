from couchdbkit.ext.django.schema import *
from dimagi.utils.couch.loosechange import map_reduce

# these are the allowable stock transaction types, listed in the
# default ordering in which they are processed. processing order
# may be customized per domain
ACTION_TYPES = [
    # indicates the product has been stocked out for N days
    # prior to the reporting date, including today ('0' does
    # not trigger an immediate stock-out)
    'stockedoutfor',

    # additions to stock
    'receipts',

    # subtractions from stock
    'consumption',

    # indicates the current stock on hand
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

    @classmethod
    def by_domain(cls, domain, wrap=True):
        """
        Gets all products in a domain.
        """
        kwargs = dict(
            view_name='commtrack/products',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        )
        if wrap:
            return Product.view(**kwargs)
        else:
            return [row["doc"] for row in Product.view(wrap_doc=False, **kwargs)]

class CommtrackActionConfig(DocumentSchema):
    action_type = StringProperty() # a value in ACTION_TYPES (could be converted to enum?)
    keyword = StringProperty()
    multiaction_keyword = StringProperty() # defaults to single-action keyword
    name = StringProperty() # defaults to action_type
    caption = StringProperty()

    def _keyword(self, multi):
        if multi:
            k = self.multiaction_keyword or self.keyword
        else:
            k = self.keyword
        return k.lower()

    @property
    def action_name(self):
        return self.name or self.action_type

class SupplyPointType(DocumentSchema):
    name = StringProperty()
    categories = StringListProperty()

class CommtrackConfig(Document):
    domain = StringProperty()

    # supported stock actions for this commtrack domain
    # listed in the order they are processed
    actions = SchemaListProperty(CommtrackActionConfig)
    # TODO must catch ambiguous action lists (two action configs with the same 'name')

    multiaction_enabled = BooleanProperty()
    multiaction_keyword = StringProperty() # if None, will attempt to parse
    # all messages as multi-action

    supply_point_types = SchemaListProperty(SupplyPointType)

    @classmethod
    def for_domain(cls, domain):
        result = cls.view("commtrack/domain_config",
                          key=[domain],
                          include_docs=True).one()
        return result

    def keywords(self, multi=False):
        return dict((action_config._keyword(multi), action_config.action_name) for action_config in self.actions)

    @property
    def actions_by_name(self):
        return dict((action_config.action_name, action_config) for action_config in self.actions)

    @property
    def known_supply_point_types(self):
        return set(spt.name for spt in self.supply_point_types)

    @property
    def supply_point_categories(self):
        return map_reduce(lambda spt: [(category, spt.name) for category in spt.categories], data=self.supply_point_types)
