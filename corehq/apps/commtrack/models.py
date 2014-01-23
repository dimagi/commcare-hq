import uuid
from xml.etree import ElementTree
from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.schema import *
from django.db import transaction
from django.utils.translation import ugettext as _
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.stock import const as stockconst
from casexml.apps.stock.consumption import ConsumptionConfiguration
from casexml.apps.stock.models import StockReport as DbStockReport, StockTransaction as DbStockTransaction
from casexml.apps.case.xml import V2
from corehq import Domain
from corehq.apps.commtrack import const
from corehq.apps.consumption.shortcuts import get_default_consumption
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch.loosechange import map_reduce
from couchforms.models import XFormInstance
from dimagi.utils import parsing as dateparse
from dimagi.utils.dates import force_to_date, force_to_datetime
from datetime import datetime
from copy import copy
from django.dispatch import receiver
from corehq.apps.locations.signals import location_created, location_edited
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.const import StockActions, RequisitionActions, RequisitionStatus, USER_LOCATION_OWNER_MAP_TYPE
from corehq.apps.commtrack.xmlutil import XML
from corehq.apps.commtrack.exceptions import LinkedSupplyPointNotFoundError

from dimagi.utils.decorators.memoized import memoized

STOCK_ACTION_ORDER = [
    StockActions.RECEIPTS,
    StockActions.CONSUMPTION,
    StockActions.STOCKONHAND,
    StockActions.STOCKOUT,
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

    @classmethod
    def by_domain(cls, domain, wrap=True):
        """
        Gets all programs in a domain.
        """
        kwargs = dict(
            view_name='commtrack/programs',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        )
        if wrap:
            return Program.view(**kwargs)
        else:
            return [row["doc"] for row in Program.view(wrap_doc=False, **kwargs)]

    @classmethod
    def get_by_code(cls, domain, code):
        result = cls.view("commtrack/program_by_code",
                          key=[domain, code],
                          include_docs=True,
                          limit=1).first()
        return result

class Product(Document):
    """
    A product, e.g. "coartem" or "tylenol"
    """
    domain = StringProperty()
    name = StringProperty()
    unit = StringProperty()
    code_ = StringProperty()
    description = StringProperty()
    category = StringProperty()
    program_id = StringProperty()
    cost = DecimalProperty()

    @property
    def code(self):
        return self.code_

    @code.setter
    def code(self, val):
        self.code_ = val.lower() if val else None

    @classmethod
    def get_by_code(cls, domain, code):
        result = cls.view("commtrack/product_by_code",
                          key=[domain, code],
                          include_docs=True).first()
        return result

    @classmethod
    def by_program_id(cls, domain, prog_id, wrap=True, **kwargs):
        kwargs.update(dict(
            view_name='commtrack/product_by_program_id',
            startkey=[domain, prog_id],
            endkey=[domain, {}],
            include_docs=True
        ))
        if wrap:
            return Product.view(**kwargs)
        else:
            return [row["doc"] for row in Product.view(wrap_doc=False, **kwargs)]

    @classmethod
    def by_domain(cls, domain, wrap=True, **kwargs):
        """
        Gets all products in a domain.
        """
        kwargs.update(dict(
            view_name='commtrack/products',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ))
        if wrap:
            return Product.view(**kwargs)
        else:
            return [row["doc"] for row in Product.view(wrap_doc=False, **kwargs)]


def product_fixture_generator(user, version, last_sync):
    if not Domain.get_by_name(user.domain).commtrack_enabled:
        return []
    root = ElementTree.Element('fixture',
                               attrib={'id': 'commtrack:products',
                                       'user_id': user.user_id})
    products = ElementTree.Element('products')
    root.append(products)
    for product_data in Product.by_domain(user.domain):
        product = (ElementTree.Element('product',
                                       {'id': product_data.get_id}))
        products.append(product)
        product_fields = ['name',
                          'unit',
                          'code',
                          'description',
                          'category',
                          'program_id',
                          'cost']
        for product_field in product_fields:
            field = ElementTree.Element(product_field)
            field.text = unicode(getattr(product_data, product_field) or '')
            product.append(field)

    return [root]


class CommtrackActionConfig(DocumentSchema):
    action = StringProperty() # one of the base stock action types (see StockActions enum)
    subaction = StringProperty() # (optional) to further distinguish different kinds of the base action
        # (i.e., separately tracking consumption as 'dispensed' or 'lost'). note that when the system
        # infers consumption/receipts from reported stock, it will be marked here as a subaction
    _keyword = StringProperty() # sms code
    caption = StringProperty() # display title

    @classmethod
    def wrap(cls, data):
        if 'action_type' in data:
            data['action'] = data['action_type']
            del data['action_type']

        if 'name' in data:
            if data['name'] == 'lost':
                data['subaction'] = 'loss'

            del data['name']

        return super(CommtrackActionConfig, cls).wrap(data)

    def __repr__(self):
        return '{action} ({subaction}): {caption} ({_keyword})'.format(**self._doc)

    @property
    def keyword(self):
        return self._keyword

    @keyword.setter
    def keyword(self, val):
        self._keyword = val.lower() if val else None

    @property
    def name(self):
        return ':'.join(filter(None, [self.action, self.subaction]))

    @property
    def is_stock(self):
        return self.action in STOCK_ACTION_ORDER

    @property
    def is_requisition(self):
        return self.action in REQUISITION_ACTION_TYPES

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
    use_supply_point_type_default_consumption = BooleanProperty(default=False)


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

    @property
    def is_configured(self):
        return True if self.enabled and self.url and self.password and self.username else False

class AlertConfig(DocumentSchema):
    stock_out_facilities = BooleanProperty(default=False)
    stock_out_commodities = BooleanProperty(default=False)
    stock_out_rates = BooleanProperty(default=False)
    non_report = BooleanProperty(default=False)

class StockRestoreConfig(DocumentSchema):

    section_to_consumption_types = DictProperty()

class CommtrackConfig(Document):

    domain = StringProperty()

    # supported stock actions for this commtrack domain
    # listed in the order they are processed -- TODO support for this custom ordering might go away
    actions = SchemaListProperty(CommtrackActionConfig)
    # TODO must catch ambiguous action lists (two action configs with the same 'name')

    multiaction_enabled = BooleanProperty()
    multiaction_keyword_ = StringProperty()

    location_types = SchemaListProperty(LocationType)
    supply_point_types = SchemaListProperty(SupplyPointType)

    requisition_config = SchemaProperty(CommtrackRequisitionConfig)
    openlmis_config = SchemaProperty(OpenLMISConfig)

    # configured on Advanced Settings page
    use_auto_emergency_levels = BooleanProperty(default=False)

    use_auto_consumption = BooleanProperty(default=False)
    consumption_config = SchemaProperty(ConsumptionConfig)
    stock_levels_config = SchemaProperty(StockLevelsConfig)
    ota_restore_config = SchemaProperty(StockRestoreConfig)

    @property
    def multiaction_keyword(self):
        return self.multiaction_keyword_

    @multiaction_keyword.setter
    def multiaction_keyword(self, val):
        self.multiaction_keyword_ = val.lower() if val else None

    # configured on Subscribe Sms page
    alert_config = SchemaProperty(AlertConfig)

    @classmethod
    def for_domain(cls, domain):
        result = cls.view("commtrack/domain_config",
                          key=[domain],
                          include_docs=True).first()
        return result

    @property
    def all_actions(self):
        return self.actions + (self.requisition_config.actions if self.requisitions_enabled else [])

    def action_by_keyword(self, keyword):
        def _action(action, type):
            action.type = type
            return action
        actions = [_action(a, 'stock') for a in self.actions]
        if self.requisitions_enabled:
            actions += [_action(a, 'req') for a in self.requisition_config.actions]
        return dict((a.keyword, a) for a in actions).get(keyword)

    def get_consumption_config(self):
        def _default_consumption_function(case_id, product_id):
            # note: for now as an optimization hack, per-supply point type is not supported
            # unless explicitly configured, because it will require looking up the case
            facility_type = None
            if self.consumption_config.use_supply_point_type_default_consumption:
                try:
                    supply_point = SupplyPointCase.get(case_id)
                    facility_type = supply_point.location.location_type
                except ResourceNotFound:
                    pass
            return get_default_consumption(self.domain, product_id, facility_type, case_id)

        return ConsumptionConfiguration(
            min_periods=self.consumption_config.min_transactions,
            min_window=self.consumption_config.min_window,
            max_window=self.consumption_config.optimal_window,
            default_consumption_function=_default_consumption_function,
        )

    def get_ota_restore_settings(self):
        # for some reason it doesn't like this import
        from casexml.apps.phone.restore import StockSettings
        return StockSettings(
            section_to_consumption_types=self.ota_restore_config.section_to_consumption_types,
            consumption_config=self.get_consumption_config(),
        )


    """
    @property
    def keywords(self):
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
    """

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


class NewStockReport(object):
    """
    Intermediate class for dealing with stock XML
    """
    # todo: fix name, remove old stock report class
    def __init__(self, form, timestamp, tag, transactions):
        self._form = form
        self.form_id = form._id
        self.timestamp = timestamp
        self.tag = tag
        self.transactions = transactions

    @classmethod
    def from_xml(cls, form, config, elem):
        tag = elem.tag
        tag = tag[tag.find('}')+1:] # strip out ns
        timestamp = force_to_datetime(elem.attrib.get('date', form.received_on))
        products = elem.findall('./{%s}entry' % const.COMMTRACK_REPORT_XMLNS)
        transactions = [t for prod_entry in products for t in
                        StockTransaction.from_xml(config, timestamp, tag, elem, prod_entry)]

        return cls(form, timestamp, tag, transactions)

    @transaction.commit_on_success
    def create_models(self):
        # todo: this function should probably move to somewhere in casexml.apps.stock
        report = DbStockReport.objects.create(form_id=self.form_id, date=self.timestamp, type=self.tag)
        for txn in self.transactions:
            db_txn = DbStockTransaction(
                report=report,
                case_id=txn.case_id,
                section_id=txn.section_id,
                product_id=txn.product_id,
            )
            previous_transaction = db_txn.get_previous_transaction()
            db_txn.type = txn.action
            db_txn.subtype = txn.subaction
            if self.tag == 'balance':
                db_txn.stock_on_hand = txn.quantity
                db_txn.quantity = 0
            else:
                assert self.tag == 'transfer'
                db_txn.quantity = txn.relative_quantity
                db_txn.stock_on_hand = (previous_transaction.stock_on_hand if previous_transaction else 0) + db_txn.quantity
            db_txn.save()


class StockTransaction(Document):
    """
    wrapper/helper for transactions
    """
    # todo: why is this a Document?
    domain = StringProperty()
    timestamp = DateTimeProperty()
    location_id = StringProperty()  # location record id
    case_id = StringProperty()
    section_id = StringProperty()
    product_id = StringProperty()
    action = StringProperty()
    subaction = StringProperty()
    quantity = DecimalProperty()
    processing_order = IntegerProperty()

    """
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
    """

    def __init__(self, **kwargs):
        def _action_def(val):
            return {
                'action': val.action,
                'subaction': val.subaction,
            }
        def _product(val):
            # FIXME want to store product in memory object (but not persist to couch...
            # is this possible in jsonobject?)
            #self.product = val
            return {
                'product_id': val._id,
            }
        def _inferred(val):
            return {
                'subaction': stockconst.TRANSACTION_SUBTYPE_INFERRED,
            }
        def _config(val):
            ret = {
                'processing_order': STOCK_ACTION_ORDER.index(kwargs['action']),
            }
            if not kwargs.get('domain'):
                ret['domain'] = val.domain
            return ret

        for name, var in locals().iteritems():
            if hasattr(var, '__call__') and name.startswith('_'):
                attr = name[1:]
                if kwargs.get(attr):
                    val = kwargs[attr]
                    del kwargs[attr]
                    kwargs.update(var(val))

        super(StockTransaction, self).__init__(**kwargs)

    @property
    def relative_quantity(self):
        """
        Gets the quantity of this transaction as a positive or negative number
        depending on the action/context
        """
        if self.action == const.StockActions.CONSUMPTION:
            return -self.quantity
        else:
            return self.quantity

    def action_config(self, commtrack_config):
        action = CommtrackActionConfig(action=self.action, subaction=self.subaction)
        for a in commtrack_config.all_actions:
            if a.name == action.name:
                return a
        return None

    @classmethod
    def from_xml(cls, config, timestamp, action_tag, action_node, product_node):
        action_type = action_node.attrib.get('type')
        subaction = action_type
        quantity = float(product_node.attrib.get('quantity'))
        def _txn(action, case_id, section_id):
            data = {
                'timestamp': timestamp,
                'product_id': product_node.attrib.get('id'),
                'quantity': quantity,
                'action': action,
                'case_id': case_id,
                'section_id': section_id,
                'subaction': subaction if subaction and subaction != action else None
                # note: no location id
            }
            return cls(config=config, **data)

        DEFAULT_SECTION_ID = 'stock'
        if action_tag == 'balance':
            yield _txn(
                action=const.StockActions.STOCKONHAND if quantity > 0 else const.StockActions.STOCKOUT,
                case_id=action_node.attrib['entity-id'],
                section_id=action_node.attrib.get('section-id', DEFAULT_SECTION_ID),
            )
        elif action_tag == 'transfer':
            src, dst = [action_node.attrib.get(k) for k in ('src', 'dest')]
            assert src or dst
            if src is not None:
                yield _txn(action=const.StockActions.CONSUMPTION, case_id=src,
                           section_id=action_node.attrib.get('section-id', DEFAULT_SECTION_ID))
            if dst is not None:
                yield _txn(action=const.StockActions.RECEIPTS, case_id=dst,
                           section_id=action_node.attrib.get('section-id', DEFAULT_SECTION_ID))

    def to_xml(self, E=None, **kwargs):
        if not E:
            E = XML()

        tx_type = 'balance' if self.action in (
            StockActions.STOCKONHAND,
            StockActions.STOCKOUT,
        ) else 'transfer'

        attr = {}
        if self.timestamp:
            attr['date'] = dateparse.json_format_datetime(self.timestamp)

        attr['section-id'] = 'stock'
        if tx_type == 'balance':
            attr['entity-id'] = self.case_id
        elif tx_type == 'transfer':
            here, there = ('dest', 'src') if self.action == StockActions.RECEIPTS else ('src', 'dest')
            attr[here] = self.case_id
            # no 'there' for now
            if self.subaction:
                attr['type'] = self.subaction

        return getattr(E, tx_type)(
            E.entry(
                id=self.product_id,
                quantity=str(self.quantity if self.action != StockActions.STOCKOUT else 0),
            ),
            **attr
        )

    @property
    def category(self):
        return 'stock'

    def fragment(self):
        """
        A short string representation of this to be used in sms correspondence
        """
        if self.quantity is not None:
            quant = int(self.quantity) if self.quantity == int(self.quantity) else self.quantity
        else:
            quant = ''
        # FIXME product fetch here is inefficient
        return '%s%s' % (Product.get(self.product_id).code.lower(), quant)

    def __repr__(self):
        return '{action} ({subaction}): {quantity} (loc: {location_id}, product: {product_id})'.format(**self._doc)


def _get_single_index(case, identifier, type, wrapper=None):
    matching = filter(lambda i: i.identifier == identifier, case.indices)
    if matching:
        assert len(matching) == 1, 'should only be one parent index'
        assert matching[0].referenced_type == type, \
             ' parent had bad case type %s' % matching[0].referenced_type
        ref_id = matching[0].referenced_id
        return wrapper.get(ref_id) if wrapper else ref_id
    return None


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

    def get_product_subcases(self):
        product_subcase_uuids = [ix.referenced_id for ix in self.reverse_indices if ix.identifier == const.PARENT_CASE_REF]
        return SupplyPointProductCase.view('_all_docs', keys=product_subcase_uuids, include_docs=True)

    def get_product_subcase(self, product_id):
        filtered = filter(lambda spp: spp.product == product_id, self.get_product_subcases())
        return filtered[0] if filtered else None

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
        return cls.view(
            'commtrack/supply_point_by_loc',
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

# TODO eliminate this
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
    product = StringProperty()  # would be nice if this was product_id but is grandfathered in
    current_stock = DecimalProperty()
    stocked_out_since = StringProperty()

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
        return float(self.current_stock) if self.current_stock is not None else None

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
            sos = datetime.strptime(self.stocked_out_since, '%Y-%m-%d').date()
            today = datetime.today().date()
            return (today - sos).days / DAYS_PER_MONTH
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

    def get_last_reported_date(self):
        last_reported = getattr(self, 'last_reported', None)
        return force_to_date(last_reported)

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

    @memoized
    def get_location(self):
        if self.location_:
            return Location.get(self.location_[-1])

    @memoized
    def get_requester(self):
        return CommCareUser.get(self.requested_by)

    def sms_format(self):
        # TODO needs fixed
        # return '%s:%s' % (self.get_product().code, self.get_default_value())
        raise NotImplementedError()

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

    def to_full_dict(self):
        # TODO verify if this needs fixed or just deleted
        raise NotImplementedError()

        #data = super(RequisitionCase, self).to_full_dict()
        #sp = self.get_supply_point_case()
        #product = self.get_product_case()
        #data['supply_point_name'] = sp['name'] if sp else ''
        #data['product_name'] = product['name'] if product else ''
        #data['balance'] = self.get_default_value()
        #return data

    @classmethod
    def get_by_external_id(cls, domain, external_id):
        return cls.view('hqcase/by_domain_external_id',
            key=[domain, external_id],
            include_docs=True, reduce=False,
            classes={'CommCareCase': RequisitionCase}
        ).all()

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


class CommTrackUser(CommCareUser):
    @classmethod
    def wrap(cls, data):
        # lazy migration from commtrack_location to locations
        if 'commtrack_location' in data:
            original_location = data['commtrack_location']
            del data['commtrack_location']

            instance = super(CommTrackUser, cls).wrap(data)

            try:
                original_location_object = Location.get(original_location)
            except ResourceNotFound:
                # if there was bad data in there before, we can ignore it
                return instance
            instance.set_locations([original_location_object])

            return instance
        else:
            return super(CommTrackUser, cls).wrap(data)

    @classmethod
    def by_domain(cls, domain, is_active=True, reduce=False, limit=None, skip=0, strict=False, doc_type=None):
        doc_type = doc_type or 'CommCareUser'
        return super(CommTrackUser, cls).by_domain(domain, is_active, reduce, limit, skip, strict, doc_type)

    def get_location_map_case(self):
        try:
            from corehq.apps.commtrack.util import location_map_case_id
            return CommCareCase.get(location_map_case_id(self))
        except ResourceNotFound:
            return None

    @property
    def location(self):
        """ Legacy method. To be removed when the site supports multiple locations """
        if self.locations:
            return self.locations[0]
        else:
            return None

    @property
    def locations(self):
        mapping = self.get_location_map_case()

        if mapping:
            return [SupplyPointCase.wrap(index.referenced_case.to_json()).location for index in mapping.indices]
        else:
            return []

    def supply_point_index_mapping(self, supply_point, clear=False):
        if supply_point:
            return {
                'supply_point-' + supply_point._id:
                (
                    supply_point.type,
                    supply_point._id if not clear else ''
                )
            }
        else:
            raise LinkedSupplyPointNotFoundError(
                "There was no linked supply point for the location."
            )

    def add_location(self, location):
        sp = location.linked_supply_point()

        from corehq.apps.commtrack.util import submit_mapping_case_block
        submit_mapping_case_block(self, self.supply_point_index_mapping(sp))

    def clear_locations(self):
        mapping = self.get_location_map_case()
        if mapping:
            mapping.delete()

    def submit_location_block(self, caseblock):
        submit_case_blocks(
            ElementTree.tostring(caseblock.as_xml()),
            self.domain,
            self.username,
            self._id
        )

    def set_locations(self, locations):
        if set([loc._id for loc in locations]) == set([loc._id for loc in self.locations]):
            # don't do anything if the list passed is the same
            # as the users current locations. the check is a little messy
            # as we can't compare the location objects themself
            return

        self.clear_locations()

        if not locations:
            return

        index = {}
        for location in locations:
            sp = SupplyPointCase.get_by_location(location)
            index.update(self.supply_point_index_mapping(sp))

        from corehq.apps.commtrack.util import location_map_case_id
        caseblock = CaseBlock(
            create=True,
            case_type=USER_LOCATION_OWNER_MAP_TYPE,
            case_id=location_map_case_id(self),
            version=V2,
            owner_id=self._id,
            index=index
        )

        self.submit_location_block(caseblock)

    def remove_location(self, location):
        sp = SupplyPointCase.get_by_location(location)

        mapping = self.get_location_map_case()

        if mapping and location._id in [loc._id for loc in self.locations]:
            caseblock = CaseBlock(
                create=False,
                case_id=mapping._id,
                version=V2,
                index=self.supply_point_index_mapping(sp, True)
            )

            self.submit_location_block(caseblock)


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
