from couchdbkit.ext.django.schema import *
from dimagi.utils.couch.loosechange import map_reduce
from couchforms.models import XFormInstance
from dimagi.utils import parsing as dateparse
from datetime import datetime
from casexml.apps.case.models import CommCareCase
from copy import copy
from django.dispatch import receiver
from corehq.apps.locations.signals import location_created

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

def _view_shared(view_name, domain, location_id=None, skip=0, limit=100):
    extras = {"limit": limit} if limit else {}
    startkey = [domain, location_id] if location_id else [domain]
    endkey = copy(startkey) + [{}]
    return CommCareCase.get_db().view(
        view_name, startkey=startkey, endkey=endkey,
        reduce=False, skip=skip, **extras)

class StockStatus(DocumentSchema):
    """
    This is a wrapper/helper class to represent the current stock status
    of a commtrack case.
    """

    current_stock = StringProperty()
    stocked_out_since = DateTimeProperty()
    product = StringProperty()
    location_path = StringListProperty(name="location_")
    server_modified_on = DateTimeProperty()

    @property
    def location_id(self):
        return self.location_path[-1]

    @classmethod
    def from_case(cls, case):
        return StockStatus.wrap(case._doc)

    @classmethod
    def wrap(cls, data):
        # couchdbkit doesn't like passing empty strings (instead of nulls)
        # to DateTimeProperty fields
        if data.get('stocked_out_since', None) == '':
            del data['stocked_out_since']
        return super(StockStatus, cls).wrap(data) 

    @classmethod
    def by_domain(cls, domain, skip=0, limit=100):
        return [StockStatus.wrap(row["value"]) for row in _view_shared(
            'commtrack/current_stock_status', domain, skip=skip, limit=limit)]

    @classmethod
    def by_location(cls, domain, location_id, skip=0, limit=100):
        return [StockStatus.wrap(row["value"]) for row in _view_shared(
            'commtrack/current_stock_status', domain, location_id,
            skip=skip, limit=limit)]

class StockTransaction(DocumentSchema):
    """
    wrapper/helper for transactions
    """

    value = IntegerProperty()
    action = StringProperty()
    location_id = StringProperty()
    product = StringProperty()
    product_entry = StringProperty()
    received_on = DateTimeProperty()
    inferred = BooleanProperty(name='@inferred', default=False)

    @classmethod
    def by_domain(cls, domain, skip=0, limit=100):
        return [StockTransaction.wrap(row["value"]) for row in _view_shared(
            'commtrack/stock_transactions', domain, skip=skip, limit=limit)]

    @classmethod
    def by_location(cls, domain, location_id, skip=0, limit=100):
        return [StockTransaction.wrap(row["value"]) for row in _view_shared(
            'commtrack/stock_transactions', domain, location_id,
            skip=skip, limit=limit)]

class StockReport(object):
    """
    This is a wrapper around the couch xform doc that gets associated with
    stock reports to provide convenient access to the underlying structure.
    """

    def __init__(self, form):
        # TODO: validation?
        self._form = form

    @property
    def id(self):
        return self._form._id

    @property
    def user_id(self):
        return self._form.metadata.userID

    @property
    def submitted_on(self):
        return self._form.metadata.timeEnd

    @property
    def received_on(self):
        return self._form.received_on

    @property
    def location_path(self):
        return self._form.location_

    @property
    def location_id(self):
        return self.location_path[-1]

    @property
    def transactions(self):
        return [StockTransaction.wrap(t) for t in \
                self._form.form.get('transaction', [])]

    @property
    def raw_form(self):
        return self._form._doc

    @classmethod
    def get(cls, id):
        return StockReport(XFormInstance.get(id))

    @classmethod
    def get_reports(cls, domain, location=None, datespan=None):
        start = datespan.startdate if datespan else datetime(1900, 1, 1)
        end = datespan.end_of_end_day if datespan else datetime.max
        timestamp_start = dateparse.json_format_datetime(start)
        timestamp_end =  dateparse.json_format_datetime(end)
        loc_id = location._id if location else None
        startkey = [domain, loc_id, timestamp_start]
        endkey = [domain, loc_id, timestamp_end]
        return [StockReport(f) for f in \
                XFormInstance.view('commtrack/stock_reports',
                                   startkey=startkey,
                                   endkey=endkey,
                                   include_docs=True)]

@receiver(location_created)
def post_loc_created(sender, loc=None, **kwargs):
    # circular imports
    from corehq.apps.commtrack.helpers import make_supply_point
    from corehq.apps.domain.models import Domain

    if not Domain.get_by_name(loc.domain).commtrack_enabled:
        return

    # exclude non-leaf locs
    if loc.location_type == 'outlet': # TODO 'outlet' is PSI-specific
        make_supply_point(loc.domain, loc)

