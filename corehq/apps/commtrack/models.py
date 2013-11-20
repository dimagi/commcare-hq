import uuid
from xml.etree import ElementTree
from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.schema import *
from django.utils.translation import ugettext as _
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2

from corehq.apps.commtrack import const
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch.loosechange import map_reduce
from couchforms.models import XFormInstance
from dimagi.utils import parsing as dateparse
from datetime import datetime
from casexml.apps.case.models import CommCareCase
from copy import copy
from django.dispatch import receiver
from corehq.apps.locations.signals import location_created, location_edited
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.const import RequisitionActions, RequisitionStatus

from dimagi.utils.decorators.memoized import memoized

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

REQUISITION_ACTION_TYPES = [
    # request a product
    RequisitionActions.REQUEST,

    # approve a requisition (it is allowed to be packed)
    # using this is configurable and optional
    RequisitionActions.APPROVAL,

    # pack a requisition (the order is ready)
    RequisitionActions.PACK,

    # receive the sock (closes the requisition)
    # NOTE: it's not totally clear if this is necessary or
    # should be built into the regular receipt workflow.
    RequisitionActions.RECEIPTS,
]


class Program(Document):
    """
    A program, e.g. "hiv" or "tb"
    """
    domain = StringProperty()
    name = StringProperty()
    code = StringProperty()
    description = StringProperty()


class Product(Document):
    """
    A product, e.g. "coartem" or "tylenol"
    """
    domain = StringProperty()
    name = StringProperty()
    unit = StringProperty()
    code = StringProperty()
    description = StringProperty()
    category = StringProperty()
    program_id = StringProperty()
    cost = DecimalProperty()

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

    def __repr__(self):
        return '{action_type}: {caption} ({keyword})'.format(**self._doc)

    def _keyword(self, multi):
        if multi:
            k = self.multiaction_keyword or self.keyword
        else:
            k = self.keyword
        return k.lower()

    @property
    def action_name(self):
        return self.name or self.action_type

    @property
    def is_stock(self):
        # NOTE: assumes ACTION_TYPES and REQUISITION_ACTION_TYPES don't overlap
        return self.action_type in ACTION_TYPES

    @property
    def is_requisition(self):
        return self.action_type in REQUISITION_ACTION_TYPES

class LocationType(DocumentSchema):
    name = StringProperty()
    allowed_parents = StringListProperty()
    administrative = BooleanProperty()

class CommtrackRequisitionConfig(DocumentSchema):
    # placeholder class for when this becomes fancier

    enabled = BooleanProperty(default=False)

    # requisitions have their own sets of actions
    actions = SchemaListProperty(CommtrackActionConfig)

    def get_sorted_actions(self):
        def _action_key(a):

            # intentionally fails hard if misconfigured.
            const.ORDERED_REQUISITION_ACTIONS.index(a.action_type)

        return sorted(self.actions, key=_action_key)

    def get_next_action(self, previous_action_type):
        sorted_actions = self.get_sorted_actions()
        sorted_types = [a.action_type for a in sorted_actions]
        next_index = sorted_types.index(previous_action_type) + 1
        return sorted_actions[next_index] if next_index < len(sorted_actions) else None


class SupplyPointType(DocumentSchema):
    name = StringProperty()
    categories = StringListProperty()


class ConsumptionConfig(DocumentSchema):
    min_transactions = IntegerProperty(default=2)
    min_window = IntegerProperty(default=10)
    optimal_window = IntegerProperty()


class StockLevelsConfig(DocumentSchema):
    emergency_level = DecimalProperty(default=0.5)  # in months
    understock_threshold = DecimalProperty(default=1.5)  # in months
    overstock_threshold = DecimalProperty(default=3)  # in months


class OpenLMISConfig(DocumentSchema):
    # placeholder class for when this becomes fancier
    enabled = BooleanProperty(default=False)

    url = StringProperty()
    username = StringProperty()
    # we store passwords in cleartext right now, but in the future may want
    # to leverage something like oauth to manage this better
    password = StringProperty()

    using_requisitions = BooleanProperty(default=False) # whether openlmis handles our requisitions for us


class CommtrackConfig(Document):

    domain = StringProperty()

    # supported stock actions for this commtrack domain
    # listed in the order they are processed
    actions = SchemaListProperty(CommtrackActionConfig)
    # TODO must catch ambiguous action lists (two action configs with the same 'name')

    multiaction_enabled = BooleanProperty()
    multiaction_keyword = StringProperty() # if None, will attempt to parse
    # all messages as multi-action

    location_types = SchemaListProperty(LocationType)
    supply_point_types = SchemaListProperty(SupplyPointType)

    requisition_config = SchemaProperty(CommtrackRequisitionConfig)
    openlmis_config = SchemaProperty(OpenLMISConfig)

    # configured on Advanced Settings page
    use_auto_emergency_levels = BooleanProperty(default=False)

    use_auto_consumption = BooleanProperty(default=False)
    consumption_config = SchemaProperty(ConsumptionConfig)
    stock_levels_config = SchemaProperty(StockLevelsConfig)

    @classmethod
    def for_domain(cls, domain):
        result = cls.view("commtrack/domain_config",
                          key=[domain],
                          include_docs=True).one()
        return result

    def all_actions(self):
        if self.requisitions_enabled:
            return self.actions + self.requisition_config.actions
        return self.actions

    def _keywords(self, action_list, multi):
        return dict((action_config._keyword(multi), action_config.action_name) \
                    for action_config in action_list)

    def keywords(self, multi=False):
        return self._keywords(self.actions, multi)

    # TODO clean all this up
    def stock_keywords(self):
        return self.keywords()
    def requisition_keywords(self):
        return self._keywords(self.requisition_config.actions if self.requisitions_enabled else [], False)

    def all_keywords(self, multi=False):
        return self._keywords(self.all_actions(), multi)

    def _by_name(self, action_list):
        return dict((action_config.action_name, action_config) for action_config in action_list)

    @property
    def actions_by_name(self):
        return self._by_name(self.actions)

    @property
    def all_actions_by_name(self):
        return self._by_name(self.all_actions())

    @property
    def all_actions_by_type(self):
        return dict((action_config.action_type, action_config) for action_config in self.all_actions())

    def get_action_by_type(self, action_type):
        return self.all_actions_by_type[action_type]

    @property
    def known_supply_point_types(self):
        return set(spt.name for spt in self.supply_point_types)

    @property
    def supply_point_categories(self):
        return map_reduce(lambda spt: [(category, spt.name) for category in spt.categories], data=self.supply_point_types)

    @property
    def requisitions_enabled(self):
        return self.requisition_config.enabled

    @property
    def openlmis_enabled(self):
        return self.openlmis_config.enabled

def _view_shared(view_name, domain, location_id=None, skip=0, limit=100):
    extras = {"limit": limit} if limit else {}
    startkey = [domain, location_id] if location_id else [domain]
    endkey = copy(startkey) + [{}]
    return CommCareCase.get_db().view(
        view_name, startkey=startkey, endkey=endkey,
        reduce=False, skip=skip, **extras)


def force_int(value):
    if value is None:
        return None
    else:
        return int(value)


def force_bool(value):
    if value is None:
        return None
    elif value is 'false':
        return False
    else:
        return bool(value)


def force_empty_string_to_null(value):
    if value == '':
        return None
    else:
        return value


class StringDataSchema(DocumentSchema):

    @classmethod
    def force_wrap(cls, data):
        data = copy(data)
        for property in cls.properties().values():
            transform = {
                IntegerProperty: force_int,
                BooleanProperty: force_bool,
                DateProperty: force_empty_string_to_null,
                DateTimeProperty: force_empty_string_to_null,
            }.get(property.__class__, lambda x: x)
            data[property.name] = transform(data.get(property.name))
        return super(StringDataSchema, cls).wrap(data)

    @classmethod
    def wrap(cls, data):
        raise NotImplementedError()


class StockStatus(StringDataSchema):
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
        return StockStatus.force_wrap(case._doc)

    @classmethod
    def by_domain(cls, domain, skip=0, limit=100):
        return [StockStatus.force_wrap(row["value"]) for row in _view_shared(
            'commtrack/current_stock_status', domain, skip=skip, limit=limit)]

    @classmethod
    def by_location(cls, domain, location_id, skip=0, limit=100):
        return [StockStatus.force_wrap(row["value"]) for row in _view_shared(
            'commtrack/current_stock_status', domain, location_id,
            skip=skip, limit=limit)]


class StockTransaction(StringDataSchema):
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
    processing_order = IntegerProperty(name='@order')

    @classmethod
    def by_domain(cls, domain, skip=0, limit=100):
        return [StockTransaction.force_wrap(row["value"]) for row in _view_shared(
            'commtrack/stock_transactions', domain, skip=skip, limit=limit)]

    @classmethod
    def by_location(cls, domain, location_id, skip=0, limit=100):
        return [StockTransaction.force_wrap(row["value"]) for row in _view_shared(
            'commtrack/stock_transactions', domain, location_id,
            skip=skip, limit=limit)]

    @classmethod
    def by_product(cls, product_case, start_date, end_date):
        q = CommCareCase.get_db().view('commtrack/stock_transactions_by_product',
                                       startkey=[product_case, start_date],
                                       endkey=[product_case, end_date, {}])
        return [StockTransaction.force_wrap(row['value']) for row in q]


def _get_single_index(case, identifier, type, wrapper=None):
    matching = filter(lambda i: i.identifier == identifier, case.indices)
    if matching:
        assert len(matching) == 1, 'should only be one parent index'
        assert matching[0].referenced_type == type, \
             ' parent had bad case type %s' % matching[0].referenced_type
        ref_id = matching[0].referenced_id
        return wrapper.get(ref_id) if wrapper else ref_id
    return None


def get_case_wrapper(data):
    return {
        const.SUPPLY_POINT_CASE_TYPE: SupplyPointCase,
        const.SUPPLY_POINT_PRODUCT_CASE_TYPE: SupplyPointProductCase,
        const.REQUISITION_CASE_TYPE: RequisitionCase
    }.get(data.get('type'))


class SupplyPointCase(CommCareCase):
    """
    A wrapper around CommCareCases to get more built in functionality
    specific to supply points.
    """

    # TODO move location_ property from CommCareCase

    class Meta: 
        # This is necessary otherwise syncdb will confuse this app with casexml
        app_label = "commtrack"

    def open_requisitions(self):
        return RequisitionCase.open_for_location(self.domain, self.location_[-1])

    @property
    @memoized
    def location(self):
        if hasattr(self, 'location_id'):
            try:
                return Location.get(self.location_id)
            except ResourceNotFound:
                pass
        return None

    @classmethod
    def _from_caseblock(cls, domain, caseblock):
        username = const.COMMTRACK_USERNAME
        casexml = ElementTree.tostring(caseblock.as_xml())
        submit_case_blocks(casexml, domain, username, const.get_commtrack_user_id(domain),
                           xmlns=const.COMMTRACK_SUPPLY_POINT_XMLNS)
        return cls.get(caseblock._id)

    @classmethod
    def create_from_location(cls, domain, location, owner_id=None):
        # a supply point is currently just a case with a special type
        id = uuid.uuid4().hex
        user_id = const.get_commtrack_user_id(domain)
        owner_id = owner_id or user_id
        kwargs = {'external_id': location.external_id} if location.external_id else {}
        caseblock = CaseBlock(
            case_id=id,
            create=True,
            version=V2,
            case_name=location.name,
            user_id=user_id,
            owner_id=owner_id,
            case_type=const.SUPPLY_POINT_CASE_TYPE,
            update={
                'location_id': location._id,
            },
            **kwargs
        )
        return cls._from_caseblock(domain, caseblock)

    def update_from_location(self, location):
        assert self.domain == location.domain
        def _are_different(supply_point, loc):
            return (supply_point.external_id != loc.external_id or
                    supply_point.name != loc.name or
                    supply_point.location_id != loc._id)

        if _are_different(self, location):
            kwargs = {'external_id': location.external_id} if location.external_id else {}
            caseblock = CaseBlock(
                case_id=self._id,
                create=False,
                version=V2,
                case_name=location.name,
                user_id=const.get_commtrack_user_id(location.domain),
                update={
                    'location_id': location._id,
                },
                **kwargs
            )
            return SupplyPointCase._from_caseblock(location.domain, caseblock)
        else:
            return self


    def to_full_dict(self):
        data = super(SupplyPointCase, self).to_full_dict()
        data.update({
            'location_type': None,
            'location_site_code': None,
            'location_parent_name': None,
        })
        if self.location:
            data['location_type'] = self.location.location_type
            data['location_site_code'] = self.location.site_code
            if self.location.parent:
                data['location_parent_name'] = self.location.parent.name

        # todo
        #data['last_reported'] = None

        return data

    @classmethod
    def get_by_location(cls, location):
        return cls.view('commtrack/supply_point_by_loc',
            key=[location.domain, location._id],
            include_docs=True,
            classes={'CommCareCase': SupplyPointCase},
        ).one()

    @classmethod
    def get_display_config(cls):
        return [
            {
                "layout": [
                    [
                        {
                            "expr": "name",
                            "name": _("Name"),
                        },
                        {
                            "expr": "location_type",
                            "name": _("Type"),
                        },
                        {
                            "expr": "location_site_code",
                            "name": _("Code"),
                        },
                        #{
                            #"expr": "last_reported",
                            #"name": _("Last Reported"),
                        #},
                    ],
                    [
                        {
                            "expr": "location_parent_name",
                            "name": _("Location"),
                        },
                        {
                            "expr": "owner_id",
                            "name": _("Group"),
                            "format": '<span data-field="owner_id">{0}</span>',
                        },
                    ],
                ],
            }
        ]

DAYS_PER_MONTH = 365.2425 / 12.

# TODO make settings

UNDERSTOCK_THRESHOLD = 0.5 # months
OVERSTOCK_THRESHOLD = 2. # months

DEFAULT_CONSUMPTION = 10. # per month

class SupplyPointProductCase(CommCareCase):
    """
    A wrapper around CommCareCases to get more built in functionality
    specific to supply point products.

    See
    https://confluence.dimagi.com/display/ctinternal/Data+Model+Documentation
    """
    class Meta: 
        # This is necessary otherwise syncdb will confuse this app with casexml
        app_label = "commtrack"

    # can flesh this out more as needed
    product = StringProperty() # would be nice if this was product_id but is grandfathered in
    current_stock = StringProperty()

    @memoized
    def get_product(self):
        return Product.get(self.product)

    @memoized
    def get_supply_point_case(self):
        return _get_single_index(self, const.PARENT_CASE_REF, const.SUPPLY_POINT_CASE_TYPE,
                                 wrapper=SupplyPointCase)

    def get_supply_point_case_id(self):
        return _get_single_index(self, const.PARENT_CASE_REF, const.SUPPLY_POINT_CASE_TYPE)

    @property
    def current_stock_level(self):
        return int(self.current_stock) if self.current_stock is not None else None

    @property
    @memoized
    def monthly_consumption(self):
        daily_rate = self.computed_.get('commtrack', {}).get('consumption_rate')
        if daily_rate is None:
            daily_rate = self.default_consumption / DAYS_PER_MONTH
        if daily_rate is None:
            return None

        return daily_rate * DAYS_PER_MONTH

    @property
    def default_consumption(self):
        # TODO does this belong in this class? in the future this will be configurable
        # based on (product, supply point type)
        return DEFAULT_CONSUMPTION

    @staticmethod
    def default_thresholds():
        return {
            'low': UNDERSTOCK_THRESHOLD,
            'high': OVERSTOCK_THRESHOLD,
        }

    @property
    def stock_thresholds(self):
        # TODO does this belong in this class? in the future will these thresholds vary
        # by supply point type? by product?
        return SupplyPointProductCase.default_thresholds()

    @staticmethod
    def months_of_stock_remaining(stock, consumption):
        try:
            return stock / consumption
        except (TypeError, ZeroDivisionError):
            return None

    @property
    def months_until_stockout(self):
        return SupplyPointProductCase.months_of_stock_remaining(self.current_stock_level, self.monthly_consumption)

    @property
    def stockout_duration_in_months(self):
        if self.stocked_out_since:
            today = datetime.today().date()
            return (today - self.stocked_out_since).days / DAYS_PER_MONTH
        else:
            return None

    @staticmethod
    def stock_category(stock, consumption, consumable_stock=None, thresholds=None):
        # "consumable stock" if the amount of stock for which we know the consumption rate
        if consumable_stock is None:
            consumable_stock = stock
        if thresholds is None:
            thresholds = SupplyPointProductCase.default_thresholds()

        if stock is None:
            return 'nodata'
        elif stock == 0:
            return 'stockout'
        elif consumption is None:
            return 'nodata'
        elif consumption == 0:
            return 'overstock'

        months_left = SupplyPointProductCase.months_of_stock_remaining(consumable_stock, consumption)
        if months_left is None:
            return 'nodata'
        elif months_left < thresholds['low']:
            return 'understock'
        elif months_left > thresholds['high']:
            return 'overstock'
        else:
            return 'adequate'

    @property
    @memoized
    def current_stock_category(self):
        return SupplyPointProductCase.stock_category(
            self.current_stock_level,
            self.monthly_consumption,
            thresholds=self.stock_thresholds
        )

    def to_full_dict(self):
        def roundif(k, digits):
            return round(k, digits) if k is not None else None

        data = super(SupplyPointProductCase, self).to_full_dict()
        del data['stocked_out_since']
        data['consumption_rate'] = self.monthly_consumption

        data['supply_point_name'] = self.get_supply_point_case()['name']
        data['product_name'] = self.get_product()['name']
        
        #data['emergency_level'] = None
        #data['max_level'] = None

        # TODO shouldn't this rounding happen in the presentation layer?
        data['months_until_stockout'] = roundif(self.months_until_stockout, 1)
        data['stockout_duration_in_months'] = roundif(self.stockout_duration_in_months, 1)

        return data

    @classmethod
    def get_display_config(cls):
        return [
            {
                "layout": [
                    [
                        {
                            "name": _("Supply Point"),
                            "expr": "supply_point_name"
                        },
                        {
                            "name": _("Product"),
                            "expr": "product_name"
                        },
                        {
                            "name": _("Last reported"),
                            "expr": "last_reported",
                            "parse_date": True
                        }
                    ],
                    [
                        {
                            "name": _("Current stock"),
                            "expr": "current_stock"
                        },
                        {
                            "name": _("Monthly consumption"),
                            "expr": "consumption_rate"
                        },
                        {
                            "name": _("Months until stockout"),
                            "expr": "months_until_stockout"
                        },
                        {
                            "name": _("Stockout duration in months"),
                            "expr": "stockout_duration_in_months"
                        }
                        #{
                            #"name": _("Emergency level"),
                            #"expr": "emergency_level"
                        #},
                        #{
                            #"name": _("Max level"),
                            #"expr": "max_level"
                        #}
                    ],
                ],
            }
        ]

    def get_json(self, lite=True):
        data = super(SupplyPointProductCase, self).get_json(lite=lite)
        data['properties'].update({
            'product': self.product,
            'current_stock': self.current_stock_level,
            'consumption': self.monthly_consumption,
            'months_remaining': self.months_until_stockout,
            'stock_category': self.current_stock_category,
        })
        return data

    # block extra couch query per case to fetch reverse index info
    @memoized
    def get_index_map(self, reversed=False):
        if reversed:
            return None
        return super(SupplyPointProductCase, self).get_index_map(reversed)


class RequisitionCase(CommCareCase):
    """
    A wrapper around CommCareCases to get more built in functionality
    specific to requisitions.
    """
    class Meta: 
        # This is necessary otherwise syncdb will confuse this app with casexml
        app_label = "commtrack"

    # supply_point = StringProperty() # todo, if desired
    requisition_status = StringProperty()

    # NOTE: this is redundant with the supply point product case and is an optimization
    product_id = StringProperty()

    # this second field is added for auditing purposes
    # the status can change, but once set - this one will not
    requested_on = DateTimeProperty()
    approved_on = DateTimeProperty()
    packed_on = DateTimeProperty()
    received_on = DateTimeProperty()

    requested_by = StringProperty()
    approved_by = StringProperty()
    packed_by = StringProperty()
    received_by = StringProperty()

    # NOTE: should these be strings or ints or decimals?
    amount_requested = StringProperty()
    # these two fields are unnecessary with no ability to
    # approve partial resupplies in the current system, but is
    # left in the models for possible use down the road
    amount_approved = StringProperty()
    amount_packed = StringProperty()
    amount_received = StringProperty()

    @memoized
    def get_location(self):
        if self.location_:
            return Location.get(self.location_[-1])

    @memoized
    def get_supply_point_case(self):
        product_case = self.get_product_case()
        if product_case:
            return product_case.get_supply_point_case()
        return None

    @memoized
    def get_product(self):
        return Product.get(self.product_id)

    @memoized
    def get_product_case(self):
        return _get_single_index(self, const.PARENT_CASE_REF,
                                 const.SUPPLY_POINT_PRODUCT_CASE_TYPE,
                                 wrapper=SupplyPointProductCase)

    def get_product_case_id(self):
        return _get_single_index(self, const.PARENT_CASE_REF,
                                 const.SUPPLY_POINT_PRODUCT_CASE_TYPE)

    @memoized
    def get_requester(self):
        return CommCareUser.get(self.requested_by)


    def get_default_value(self):
        """get how much the default is. this is dependent on state."""
        property_map = {
            RequisitionStatus.REQUESTED: 'amount_requested',
            RequisitionStatus.APPROVED: 'amount_approved',
            RequisitionStatus.PACKED: 'amount_packed',
        }
        return getattr(self, property_map.get(self.requisition_status, 'amount_requested'))

    def sms_format(self):
        return '%s:%s' % (self.get_product().code, self.get_default_value())

    def get_next_action(self):
        req_config = CommtrackConfig.for_domain(self.domain).requisition_config
        return req_config.get_next_action(
            RequisitionStatus.to_action_type(self.requisition_status)
        )

    @classmethod
    def open_for_location(cls, domain, location_id):
        """
        For a given location, return the IDs of all open requisitions at that location.
        """
        results = cls.get_db().view('commtrack/requisitions',
            endkey=[domain, location_id, 'open'],
            startkey=[domain, location_id, 'open', {}],
            reduce=False,
            descending=True,
        )
        return [r['id'] for r in results]


    @classmethod
    def open_for_product_case(cls, domain, location, product_case_id):
        """
        For a given product case, return the IDs of all open requisitions at that location.
        """
        startkey = [domain, location, 'open', product_case_id]
        results = cls.get_db().view('commtrack/requisitions',
            endkey=startkey, # yes this is confusing, but i blame couch's descending=true rules
            startkey=startkey + [{}],
            descending=True,
            reduce=False,
        )
        return [r['id'] for r in results]

    def to_full_dict(self):
        data = super(RequisitionCase, self).to_full_dict()
        sp = self.get_supply_point_case()
        product = self.get_product_case()
        data['supply_point_name'] = sp['name'] if sp else ''
        data['product_name'] = product['name'] if product else ''
        data['balance'] = self.get_default_value()
        return data

    @classmethod
    def get_by_external_id(cls, domain, external_id):
        return cls.view('commtrack/requisition_by_external',
                        key=[domain, external_id],
                        inlude_docs=True)

    @classmethod
    def get_display_config(cls):
        return [
            {
                "layout": [
                    [
                        {
                            "name": _("Supply Point"),
                            "expr": "supply_point_name"
                        }
                    ],
                    [
                        {
                            "name": _("Product"),
                            "expr": "product_name"
                        }
                    ],
                    [
                        {
                            "name": _("Status"),
                            "expr": "requisition_status"
                        }
                    ],
                    [
                        {
                            "name": _("Balance"),
                            "expr": "balance"
                        }
                    ]
                ]
            },
            {
                "layout": [
                    [ 
                        {
                            "name": _("Amount Requested"),
                            "expr": "amount_requested",
                        },
                        {
                            "name": _("Requested On"),
                            "expr": "requested_on",
                            "parse_date": True
                        }
                    ],
                    [
                        {
                            "name": _("Amount Approved"),
                            "expr": "amount_approved",
                        },
                        {
                            "name": _("Approved On"),
                            "expr": "approved_on",
                            "parse_date": True
                        }
                    ],
                    [
                        {
                            "name": _("Amount Received"),
                            "expr": "amount_Received"
                        },
                        {
                            "name": _("Received On"),
                            "expr": "received_on",
                            "parse_date": True
                        }
                    ]
                ]
            }
        ]


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
        return [StockTransaction.force_wrap(t) for t in \
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

def sync_location_supply_point(loc):
    # circular import
    from corehq.apps.domain.models import Domain

    domain = Domain.get_by_name(loc.domain)
    if not domain.commtrack_enabled:
        return

    def _needs_supply_point(loc, config):
        """Exclude administrative-only locs"""
        return loc.location_type in [loc_type.name for loc_type in config.location_types if not loc_type.administrative]

    config = domain.commtrack_settings
    if _needs_supply_point(loc, config):
        supply_point = SupplyPointCase.get_by_location(loc)
        if supply_point:
            supply_point.update_from_location(loc)
            return supply_point
        else:
            return SupplyPointCase.create_from_location(loc.domain, loc)

@receiver(location_edited)
def post_loc_edited(sender, loc=None, **kwargs):
    sync_location_supply_point(loc)

@receiver(location_created)
def post_loc_created(sender, loc=None, **kwargs):
    sync_location_supply_point(loc)

# import signals
from . import signals
