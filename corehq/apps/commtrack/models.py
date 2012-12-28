from couchdbkit.ext.django.schema import *
from couchforms.models import XFormInstance
from dimagi.utils import parsing as dateparse
from datetime import datetime
from casexml.apps.case.models import CommCareCase
from copy import copy

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

class CommtrackConfig(Document):
    domain = StringProperty()

    # supported stock actions for this commtrack domain
    # listed in the order they are processed
    actions = SchemaListProperty(CommtrackActionConfig)
    # TODO must catch ambiguous action lists (two action configs with the same 'name')

    multiaction_enabled = BooleanProperty()
    multiaction_keyword = StringProperty() # if None, will attempt to parse
    # all messages as multi-action

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


def _view_shared(view_name, domain, location_id=None, skip=0, limit=100):
    extras = {"limit": limit} if limit else {}
    startkey = [domain, location_id] if location_id else [domain]
    endkey = copy(startkey) + [{}]
    return CommCareCase.get_db().view(
        view_name, startkey=startkey, endkey=endkey,
        reduce=False, skip=skip, **extras)

class StockStatus(object):
    """
    This is a wrapper/helper class to represent the current stock status
    of a commtrack case.
    """

    def __init__(self, dict):
        self.id = dict["_id"]
        self.current_stock = dict["current_stock"]
        self.stocked_out_since = dict["stocked_out_since"] or None
        self.product_id = dict["product"]
        self.location_path = dict["location_"]
        self.server_modified_on = dict["server_modified_on"]

        # computed
        self.location_id = self.location_path[-1]

    @classmethod
    def from_case(cls, case):
        return StockStatus(case._doc)

    @classmethod
    def by_domain(cls, domain, skip=0, limit=100):
        return [StockStatus(row["value"]) for row in _view_shared(
            'commtrack/current_stock_status', domain, skip=skip, limit=limit)]

    @classmethod
    def by_location(cls, domain, location_id, skip=0, limit=100):
        return [StockStatus(row["value"]) for row in _view_shared(
            'commtrack/current_stock_status', domain, location_id,
            skip=skip, limit=limit)]

class StockTransaction(object):
    """
    wrapper/helper for transactions
    """

    def __init__(self, dict):
        self.value = dict.get('value')
        self.action = dict.get('action')
        self.location_id = dict.get('location_id')
        self.product_id = dict.get('product')
        self.product_entry_id = dict.get('product_entry')
        self.received_on = dict.get('received_on')
        self.inferred = dict.get('@inferred', False)

    @classmethod
    def by_domain(cls, domain, skip=0, limit=100):
        return [StockTransaction(row["value"]) for row in _view_shared(
            'commtrack/stock_transactions', domain, skip=skip, limit=limit)]

    @classmethod
    def by_location(cls, domain, location_id, skip=0, limit=100):
        return [StockTransaction(row["value"]) for row in _view_shared(
            'commtrack/stock_transactions', domain, location_id,
            skip=skip, limit=limit)]

# TODO: tweak this and get it working
#class StockReport(object):
#    """
#    This is a wrapper around the couch xform doc that gets associated with
#    stock reports to provide convenient access to the underlying structure.
#    """
#
#    def __init__(self, form):
#        # TODO: validation?
#        self._form = form
#
#    @property
#    def raw_form(self):
#        return self._form._doc
#
#    @classmethod
#    def get(cls, id):
#        return StockReport(XFormInstance.get(id))
#
#    @classmethod
#    def get_reports(cls, domain, location=None, datespan=None):
#        # TODO: replace reports.commtrack.psi_prototype.get_stock_reports with this
#        start = datespan.startdate if datespan else datetime.min()
#        end = datespan.end_of_end_day if datespan else datetime.max()
#        timestamp_start = dateparse.json_format_datetime(start)
#        timestamp_end =  dateparse.json_format_datetime(end)
#        loc_id = location._id if location else None
#        startkey = [domain, loc_id, timestamp_start]
#        endkey = [domain, loc_id, timestamp_end]
#        return [StockReport(f) for f in \
#                XFormInstance.view('commtrack/stock_reports',
#                                   startkey=startkey,
#                                   endkey=endkey,
#                                   include_docs=True)]
