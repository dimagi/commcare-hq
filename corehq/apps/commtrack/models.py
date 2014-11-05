from decimal import Decimal
import uuid
from xml.etree import ElementTree
from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.schema import *
from django.db import transaction
from django.utils.translation import ugettext as _
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.stock import const as stockconst
from casexml.apps.stock.consumption import (ConsumptionConfiguration, compute_default_monthly_consumption,
    compute_daily_consumption)
from casexml.apps.stock.models import StockReport as DbStockReport, StockTransaction as DbStockTransaction, DocDomainMapping
from casexml.apps.case.xml import V2
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from corehq.apps.commtrack import const
from corehq.apps.consumption.shortcuts import get_default_monthly_consumption
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from casexml.apps.stock.utils import months_of_stock_remaining, state_stock_category
from corehq.apps.domain.models import Domain
from couchforms.signals import xform_archived, xform_unarchived
from dimagi.utils.couch.database import iter_docs
from dimagi.utils import parsing as dateparse
from datetime import datetime
from copy import copy
from django.dispatch import receiver
from corehq.apps.locations.signals import location_created, location_edited
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.commtrack.const import StockActions, RequisitionActions, RequisitionStatus, USER_LOCATION_OWNER_MAP_TYPE, DAYS_IN_MONTH
from corehq.apps.commtrack.xmlutil import XML
from corehq.apps.commtrack.exceptions import LinkedSupplyPointNotFoundError, InvalidProductException
from couchexport.models import register_column_type, ComplexExportColumn
from dimagi.utils.dates import force_to_datetime
from django.db import models
from django.db.models.signals import post_save, post_delete
from dimagi.utils.parsing import json_format_datetime

from dimagi.utils.decorators.memoized import memoized
import json_field

STOCK_ACTION_ORDER = [
    StockActions.RECEIPTS,
    StockActions.CONSUMPTION,
    StockActions.STOCKONHAND,
    StockActions.STOCKOUT,
]

REQUISITION_ACTION_TYPES = [
    # request a product
    RequisitionActions.REQUEST,

    # approve a requisition (it is allowed to be fulfilled)
    # this is optional and depends on app config
    RequisitionActions.APPROVAL,

    # fulfill a requisition (order is ready)
    RequisitionActions.FULFILL,

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
    last_modified = DateTimeProperty()
    default = BooleanProperty(default=False)
    is_archived = BooleanProperty(default=False)

    def save(self, *args, **kwargs):
        self.last_modified = datetime.now()

        return super(Program, self).save(*args, **kwargs)

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
    def default_for_domain(cls, domain):
        programs = cls.by_domain(domain)
        for p in programs:
            if p.default:
                return p

    def delete(self):
        # you cannot delete the default program
        if self.default:
            raise Exception(_('You cannot delete the default program'))

        default = Program.default_for_domain(self.domain)

        products = Product.by_program_id(
            self.domain,
            self._id,
            wrap=False
        )
        to_save = []

        for product in products:
            product['program_id'] = default._id
            to_save.append(product)

            # break up saving in case there are many products
            if to_save > 500:
                Product.get_db().bulk_save(to_save)
                to_save = []

        Product.get_db().bulk_save(to_save)

        # bulk update sqlproducts
        SQLProduct.objects.filter(program_id=self._id).update(program_id=default._id)

        return super(Program, self).delete()

    def unarchive(self):
        """
        Unarchive a program, causing it (and its data) to show
        up in Couch and SQL views again.
        """
        self.is_archived = False
        self.save()

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
    code_ = StringProperty()  # todo: why the hell is this code_ and not code
    description = StringProperty()
    category = StringProperty()
    program_id = StringProperty()
    cost = DecimalProperty()
    product_data = DictProperty()
    is_archived = BooleanProperty(default=False)
    last_modified = DateTimeProperty()

    def _sync_product(self):
        properties_to_sync = [
            ('product_id', '_id'),
            'domain',
            'name',
            'is_archived',
            ('code', 'code_'),
            'description',
            'category',
            'program_id',
            'cost',
            ('units', 'unit'),
            'product_data',
        ]

        # sync properties to SQL version
        sql_product, _ = SQLProduct.objects.get_or_create(
            product_id=self._id
        )

        for prop in properties_to_sync:
            if isinstance(prop, tuple):
                sql_prop, couch_prop = prop
            else:
                sql_prop = couch_prop = prop

            if hasattr(self, couch_prop):
                setattr(sql_product, sql_prop, getattr(self, couch_prop))

        sql_product.save()

    def save(self, *args, **kwargs):
        """
        Saving a couch version of Product will trigger
        one way syncing to the SQLProduct version of this
        product.
        """
        # mark modified time stamp for selective syncing
        self.last_modified = datetime.now()

        # generate code if user didn't specify one
        if not self.code:
            from corehq.apps.commtrack.util import generate_code
            self.code = generate_code(
                self.name,
                SQLProduct.objects
                    .filter(domain=self.domain)
                    .values_list('code', flat=True)
                    .distinct()
            )

        result = super(Product, self).save(*args, **kwargs)

        self._sync_product()

        return result

    @property
    def code(self):
        return self.code_

    @code.setter
    def code(self, val):
        self.code_ = val.lower() if val else None

    @classmethod
    def get_by_code(cls, domain, code):
        if not code:
            return None
        result = cls.view("commtrack/product_by_code",
                          key=[domain, code.lower()],
                          include_docs=True).first()
        return result

    @classmethod
    def by_program_id(cls, domain, prog_id, wrap=True, **kwargs):
        kwargs.update(dict(
            view_name='commtrack/product_by_program_id',
            key=[domain, prog_id],
            include_docs=True
        ))
        if wrap:
            return Product.view(**kwargs)
        else:
            return [row["doc"] for row in Product.view(wrap_doc=False, **kwargs)]

    @classmethod
    def by_domain(cls, domain, wrap=True, include_archived=False, **kwargs):
        """
        Gets all products in a domain.

        By default this filters out any archived products.
        """
        kwargs.update(dict(
            view_name='commtrack/products',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ))
        if wrap:
            products = Product.view(**kwargs)
            if not include_archived:
                return filter(lambda p: not p.is_archived, products)
            else:
                return products
        else:
            if not include_archived:
                return [
                    row["doc"] for row in Product.view(
                        wrap_doc=False,
                        **kwargs
                    ) if not row["doc"].get('is_archived', False)
                ]
            else:
                return [
                    row["doc"] for row in Product.view(
                        wrap_doc=False,
                        **kwargs
                    )
                ]

    @classmethod
    def archived_by_domain(cls, domain, wrap=True, **kwargs):
        products = cls.by_domain(domain, wrap, kwargs)
        if wrap:
            return filter(lambda p: p.is_archived, products)
        else:
            return [p for p in products if p.get('is_archived', False)]

    @classmethod
    def ids_by_domain(cls, domain):
        """
        Gets all product ids in a domain.
        """
        view_results = Product.get_db().view('commtrack/products',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=False,
        )
        return [row['id'] for row in view_results]

    @classmethod
    def count_by_domain(cls, domain):
        """
        Gets count of products in a domain
        """
        # todo: we should add a reduce so we can get this out of couch
        return len(cls.ids_by_domain(domain))

    @classmethod
    def _export_attrs(cls):
        return [
            ('name', unicode),
            ('unit', unicode),
            'description',
            'category',
            'program_id',
            ('cost', lambda a: Decimal(a) if a else None),
        ]

    def to_dict(self):
        from corehq.apps.commtrack.util import encode_if_needed
        product_dict = {}

        product_dict['id'] = self._id
        product_dict['product_id'] = self.code_

        for attr in self._export_attrs():
            real_attr = attr[0] if isinstance(attr, tuple) else attr
            product_dict[real_attr] = encode_if_needed(
                getattr(self, real_attr)
            )

        return product_dict

    def custom_property_dict(self):
        from corehq.apps.commtrack.util import encode_if_needed
        property_dict = {}

        for prop, val in self.product_data.iteritems():
            property_dict['data: ' + prop] = encode_if_needed(val)

        return property_dict

    def archive(self):
        """
        Mark a product as archived. This will cause it (and its data)
        to not show up in default Couch and SQL views.
        """
        self.is_archived = True
        self.save()

    def unarchive(self):
        """
        Unarchive a product, causing it (and its data) to show
        up in Couch and SQL views again.
        """
        self.is_archived = False
        self.save()

    @classmethod
    def from_excel(cls, row, custom_data_validator):
        if not row:
            return None

        id = row.get('id')
        if id:
            p = cls.get(id)
        else:
            p = cls()

        p.code = str(row.get('product_id') or '')

        for attr in cls._export_attrs():
            key = attr[0] if isinstance(attr, tuple) else attr
            if key in row:
                val = row[key]
                if val is None:
                    val = ''
                if isinstance(attr, tuple):
                    val = attr[1](val)
                setattr(p, key, val)
            else:
                break

        if not p.code:
            raise InvalidProductException(_('Product ID is a required field and cannot be blank!'))
        if not p.name:
            raise InvalidProductException(_('Product name is a required field and cannot be blank!'))

        custom_data = row.get('data', {})
        error = custom_data_validator(custom_data)
        if error:
            raise InvalidProductException(error)

        p.product_data = custom_data
        p.product_data.update(row.get('uncategorized_data', {}))

        return p


class CommtrackActionConfig(DocumentSchema):
    # one of the base stock action types (see StockActions enum)
    action = StringProperty()
    # (optional) to further distinguish different kinds of the base action
    # (i.e., separately tracking consumption as 'dispensed' or 'lost'). note that when the system
    # infers consumption/receipts from reported stock, it will be marked here as a subaction
    subaction = StringProperty()
    # sms code
    _keyword = StringProperty()
    # display title
    caption = StringProperty()

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
    code = StringProperty()
    allowed_parents = StringListProperty()
    administrative = BooleanProperty()

    @classmethod
    def wrap(cls, obj):
        from corehq.apps.commtrack.util import unicode_slug
        if not obj.get('code'):
            obj['code'] = unicode_slug(obj['name'])
        return super(LocationType, cls).wrap(obj)


class CommtrackRequisitionConfig(DocumentSchema):
    # placeholder class for when this becomes fancier
    enabled = BooleanProperty(default=False)

    # requisitions have their own sets of actions
    actions = SchemaListProperty(CommtrackActionConfig)

    def get_sorted_actions(self):
        def _action_key(a):
            # intentionally fails hard if misconfigured.
            return const.ORDERED_REQUISITION_ACTIONS.index(a.action)

        return sorted(self.actions, key=_action_key)

    def get_next_action(self, previous_action_type):
        sorted_actions = self.get_sorted_actions()
        sorted_types = [a.action for a in sorted_actions]
        if previous_action_type in sorted_types:
            next_index = sorted_types.index(previous_action_type) + 1
            return sorted_actions[next_index] if next_index < len(sorted_actions) else None
        else:
            return None


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
    force_consumption_case_types = ListProperty()
    use_dynamic_product_list = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, obj):
        # todo: remove this cruft at some point
        if 'force_to_consumption_case_types' in obj:
            realval = obj['force_to_consumption_case_types']
            oldval = obj.get('force_consumption_case_types')
            if realval and not oldval:
                obj['force_consumption_case_types'] = realval
                del obj['force_to_consumption_case_types']
        return super(StockRestoreConfig, cls).wrap(obj)


class CommtrackConfig(CachedCouchDocumentMixin, Document):
    domain = StringProperty()

    # supported stock actions for this commtrack domain
    # listed in the order they are processed -- TODO support for this custom ordering might go away
    actions = SchemaListProperty(CommtrackActionConfig)
    # TODO must catch ambiguous action lists (two action configs with the same 'name')

    multiaction_enabled = BooleanProperty()
    multiaction_keyword_ = StringProperty()

    location_types = SchemaListProperty(LocationType)

    requisition_config = SchemaProperty(CommtrackRequisitionConfig)
    openlmis_config = SchemaProperty(OpenLMISConfig)

    # configured on Advanced Settings page
    use_auto_emergency_levels = BooleanProperty(default=False)

    sync_location_fixtures = BooleanProperty(default=True)
    sync_consumption_fixtures = BooleanProperty(default=True)
    use_auto_consumption = BooleanProperty(default=False)
    consumption_config = SchemaProperty(ConsumptionConfig)
    stock_levels_config = SchemaProperty(StockLevelsConfig)
    ota_restore_config = SchemaProperty(StockRestoreConfig)
    individual_consumption_defaults = BooleanProperty(default=False)

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
        def _default_monthly_consumption(case_id, product_id):
            # note: for now as an optimization hack, per-supply point type is not supported
            # unless explicitly configured, because it will require looking up the case
            facility_type = None
            if self.consumption_config.use_supply_point_type_default_consumption:
                try:
                    supply_point = SupplyPointCase.get(case_id)
                    facility_type = supply_point.location.location_type
                except ResourceNotFound:
                    pass
            return get_default_monthly_consumption(self.domain, product_id, facility_type, case_id)

        return ConsumptionConfiguration(
            min_periods=self.consumption_config.min_transactions,
            min_window=self.consumption_config.min_window,
            max_window=self.consumption_config.optimal_window,
            default_monthly_consumption_function=_default_monthly_consumption,
        )

    def get_ota_restore_settings(self):
        # for some reason it doesn't like this import
        from casexml.apps.phone.restore import StockSettings
        default_product_ids = Product.ids_by_domain(self.domain) \
            if self.ota_restore_config.use_dynamic_product_list else []
        case_filter = lambda case: case.type in set(self.ota_restore_config.force_consumption_case_types)
        return StockSettings(
            section_to_consumption_types=self.ota_restore_config.section_to_consumption_types,
            consumption_config=self.get_consumption_config(),
            default_product_list=default_product_ids,
            force_consumption_case_filter=case_filter,
        )

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
        timestamp = force_to_datetime(elem.attrib.get('date') or form.received_on).replace(tzinfo=None)
        products = elem.findall('./{%s}entry' % stockconst.COMMTRACK_REPORT_XMLNS)
        transactions = [t for prod_entry in products for t in
                        StockTransaction.from_xml(config, timestamp, tag, elem, prod_entry)]

        return cls(form, timestamp, tag, transactions)

    @transaction.commit_on_success
    def create_models(self, domain=None):
        # todo: this function should probably move to somewhere in casexml.apps.stock
        if self.tag not in stockconst.VALID_REPORT_TYPES:
            return
        report = DbStockReport.objects.create(
            form_id=self.form_id,
            date=self.timestamp,
            type=self.tag,
            domain=self._form.domain,
        )
        for txn in self.transactions:
            db_txn = DbStockTransaction(
                report=report,
                case_id=txn.case_id,
                section_id=txn.section_id,
                product_id=txn.product_id,
            )
            if domain:
                # set this as a shortcut for post save signal receivers
                db_txn.domain = domain
            previous_transaction = db_txn.get_previous_transaction()
            db_txn.type = txn.action
            db_txn.subtype = txn.subaction
            if self.tag == stockconst.REPORT_TYPE_BALANCE:
                db_txn.stock_on_hand = txn.quantity
                db_txn.quantity = 0
            else:
                assert self.tag == stockconst.REPORT_TYPE_TRANSFER
                db_txn.quantity = txn.relative_quantity
                db_txn.stock_on_hand = (previous_transaction.stock_on_hand if previous_transaction else 0) + db_txn.quantity
            db_txn.save()


class StockTransaction(object):
    """
    Helper class for transactions
    """
    action = None
    subaction = None
    quantity = None
    location_id = None
    product = None
    timestamp = None

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

        for k, v in kwargs.items():
            setattr(self, k, v)

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

    @property
    def date(self):
        if self.timestamp:
            return dateparse.json_format_datetime(self.timestamp)

    @classmethod
    def from_xml(cls, config, timestamp, action_tag, action_node, product_node):
        action_type = action_node.attrib.get('type')
        subaction = action_type
        product_id = product_node.attrib.get('id')

        def _txn(action, case_id, section_id, quantity):
            # warning: here be closures
            quantity = Decimal(str(quantity)) if quantity is not None else None
            data = {
                'timestamp': timestamp,
                'product_id': product_id,
                'quantity': quantity,
                'action': action,
                'case_id': case_id,
                'section_id': section_id,
                'subaction': subaction if subaction and subaction != action else None
                # note: no location id
            }
            return cls(config=config, **data)

        def _yield_txns(section_id, quantity):
            # warning: here be closures
            if action_tag == 'balance':
                case_id = action_node.attrib['entity-id']
                yield _txn(
                    action=const.StockActions.STOCKONHAND if quantity > 0 else const.StockActions.STOCKOUT,
                    case_id=case_id,
                    section_id=section_id,
                    quantity=quantity,
                )
            elif action_tag == 'transfer':
                src, dst = [action_node.attrib.get(k) for k in ('src', 'dest')]
                assert src or dst
                if src is not None:
                    yield _txn(action=const.StockActions.CONSUMPTION, case_id=src,
                               section_id=section_id, quantity=quantity)
                if dst is not None:
                    yield _txn(action=const.StockActions.RECEIPTS, case_id=dst,
                               section_id=section_id, quantity=quantity)

        section_id = action_node.attrib.get('section-id', None)
        grouped_entries = section_id is not None
        if grouped_entries:
            quantity = float(product_node.attrib.get('quantity'))
            for txn in _yield_txns(section_id, quantity):
                yield txn

        else:
            values = [child for child in product_node]
            for value in values:
                section_id = value.attrib.get('section-id')
                quantity = float(value.attrib.get('quantity'))
                for txn in _yield_txns(section_id, quantity):
                    yield txn

    def to_xml(self, E=None, **kwargs):
        if not E:
            E = XML()

        return E.entry(
            id=self.product_id,
            quantity=str(self.quantity if self.action != StockActions.STOCKOUT else 0),
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
        return '{action} ({subaction}): {quantity} (loc: {location_id}, product: {product_id})'.format(
            action=self.action,
            subaction=self.subaction,
            quantity=self.quantity,
            location_id=self.location_id,
            product_id=self.product_id,
        )


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

    class Meta:
        # This is necessary otherwise syncdb will confuse this app with casexml
        app_label = "commtrack"

    def open_requisitions(self):
        return RequisitionCase.open_for_location(self.domain, self.location_id)

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
        casexml = ElementTree.tostring(caseblock.as_xml(format_datetime=dateparse.json_format_datetime))
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
    def get_location_map_by_domain(cls, domain):
        """
        Returns a dict that maps from associated location id's
        to supply point id's for all supply point cases in the passed
        domain.
        """
        kwargs = dict(
            view_name='commtrack/supply_point_by_loc',
            startkey=[domain],
            endkey=[domain, {}],
        )

        return dict(
            (row['key'][1], row['id']) for row in cls.get_db().view(**kwargs)
        )

    @classmethod
    def get_by_location(cls, location):
        return cls.view(
            'commtrack/supply_point_by_loc',
            key=[location.domain, location._id],
            include_docs=True,
            classes={'CommCareCase': SupplyPointCase},
        ).one()

    @classmethod
    def get_or_create_by_location(cls, location):
        sp = cls.get_by_location(location)
        if not sp:
            sp = SupplyPointCase.create_from_location(
                location.domain,
                location
            )

        return sp

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


UNDERSTOCK_THRESHOLD = 0.5  # months
OVERSTOCK_THRESHOLD = 2.  # months
DEFAULT_CONSUMPTION = 10.  # per month


class RequisitionCase(CommCareCase):
    """
    A wrapper around CommCareCases to get more built in functionality
    specific to requisitions.
    """
    class Meta:
        # This is necessary otherwise syncdb will confuse this app with casexml
        app_label = "commtrack"

    requisition_status = StringProperty()

    # TODO none of these properties are supported on mobile currently
    # we need to discuss what will be eventually so we know what we need
    # to support here
    requested_on = DateTimeProperty()
    approved_on = DateTimeProperty()
    fulfilled_on = DateTimeProperty()
    received_on = DateTimeProperty()
    requested_by = StringProperty()
    approved_by = StringProperty()
    fulfilled_by = StringProperty()
    received_by = StringProperty()

    @memoized
    def get_location(self):
        try:
            return SupplyPointCase.get(self.indices[0].referenced_id).location
        except ResourceNotFound:
            return None

    @memoized
    def get_requester(self):
        # TODO this doesn't get set by mobile yet
        # if self.requested_by:
        #     return CommCareUser.get(self.requested_by)
        return None

    def sms_format(self):
        if self.requisition_status == RequisitionStatus.REQUESTED:
            section = 'ct-requested'
        elif self.requisition_status == RequisitionStatus.APPROVED:
            section = 'ct-approved'
        else:
            section = 'stock'

        formatted_strings = []
        states = StockState.objects.filter(
            case_id=self._id,
            section_id=section
        )
        for state in states:
            product = Product.get(state.product_id)
            formatted_strings.append(
                '%s:%d' % (product.code, state.stock_on_hand)
            )
        return ' '.join(sorted(formatted_strings))

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
        try:
            sp_id = Location.get(location_id).linked_supply_point()._id
        except ResourceNotFound:
            return []

        results = cls.get_db().view(
            'commtrack/requisitions',
            endkey=[domain, sp_id, 'open'],
            startkey=[domain, sp_id, 'open', {}],
            reduce=False,
            descending=True,
        )
        return [r['id'] for r in results]

    @classmethod
    def get_by_external_id(cls, domain, external_id):
        # only used by openlmis
        raise NotImplementedError()

        # return cls.view('hqcase/by_domain_external_id',
        #     key=[domain, external_id],
        #     include_docs=True, reduce=False,
        #     classes={'CommCareCase': RequisitionCase}
        # ).all()

    @classmethod
    def get_display_config(cls):
        return [
            {
                "layout": [
                    [
                        {
                            "name": _("Status"),
                            "expr": "requisition_status"
                        }
                    ],
                ]
            },
            {
                "layout": [
                    [
                        {
                            "name": _("Requested On"),
                            "expr": "requested_on",
                            "parse_date": True
                        },
                        {
                            "name": _("requested_by"),
                            "expr": "requested_by"
                        }
                    ],
                    [
                        {
                            "name": _("Approved On"),
                            "expr": "approved_on",
                            "parse_date": True
                        },
                        {
                            "name": _("approved_by"),
                            "expr": "approved_by"
                        }
                    ],
                    [
                        {
                            "name": _("Received On"),
                            "expr": "received_on",
                            "parse_date": True
                        },
                        {
                            "name": _("received_by"),
                            "expr": "received_by"
                        }
                    ]
                ]
            }
        ]


class RequisitionTransaction(StockTransaction):
    @property
    def category(self):
        return 'requisition'


class CommTrackUser(CommCareUser):
    class Meta:
        # This is necessary otherwise syncdb will confuse this app with users
        app_label = "commtrack"


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

    def get_linked_supply_point_ids(self):
        mapping = self.get_location_map_case()
        if mapping:
            return [index.referenced_id for index in mapping.indices]
        return []

    def get_linked_supply_points(self):
        for doc in iter_docs(CommCareCase.get_db(), self.get_linked_supply_point_ids()):
            yield SupplyPointCase.wrap(doc)

    @property
    def locations(self):
        def _gen():
            location_ids = [sp.location_id for sp in self.get_linked_supply_points()]
            for doc in iter_docs(Location.get_db(), location_ids):
                yield Location.wrap(doc)

        return list(_gen())

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

    def add_location(self, location, create_sp_if_missing=False):
        sp = SupplyPointCase.get_or_create_by_location(location)

        from corehq.apps.commtrack.util import submit_mapping_case_block
        submit_mapping_case_block(self, self.supply_point_index_mapping(sp))

    def clear_locations(self):
        mapping = self.get_location_map_case()
        if mapping:
            mapping.delete()

    def submit_location_block(self, caseblock):
        submit_case_blocks(
            ElementTree.tostring(caseblock.as_xml(format_datetime=json_format_datetime)),
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


class SQLProduct(models.Model):
    """
    A SQL based clone of couch Products.

    This is used to efficiently filter StockState and other
    SQL based queries to exclude data for archived products.
    """
    domain = models.CharField(max_length=255, db_index=True)
    product_id = models.CharField(max_length=100, db_index=True, unique=True)
    name = models.CharField(max_length=100, null=True)
    is_archived = models.BooleanField(default=False)
    code = models.CharField(max_length=100, default='', null=True)
    description = models.CharField(max_length=100, null=True, default='')
    category = models.CharField(max_length=100, null=True, default='')
    program_id = models.CharField(max_length=100, null=True, default='')
    cost = models.DecimalField(max_digits=20, decimal_places=5, null=True)
    units = models.CharField(max_length=100, null=True, default='')
    product_data = json_field.JSONField(
        default={},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    def __repr__(self):
        return "<SQLProduct(domain=%s, name=%s)>" % (
            self.domain,
            self.name
        )


class ActiveManager(models.Manager):
    """
    Filter any object that is associated to an archived product.
    """

    def get_query_set(self):
        return super(ActiveManager, self).get_query_set() \
            .exclude(sql_product__is_archived=True) \
            .exclude(sql_location__is_archived=True)


class StockState(models.Model):
    """
    Read only reporting model for keeping computed stock states per case/product
    """
    section_id = models.CharField(max_length=100, db_index=True)
    case_id = models.CharField(max_length=100, db_index=True)
    product_id = models.CharField(max_length=100, db_index=True)
    stock_on_hand = models.DecimalField(max_digits=20, decimal_places=5, default=Decimal(0))
    daily_consumption = models.DecimalField(max_digits=20, decimal_places=5, null=True)
    last_modified_date = models.DateTimeField()
    sql_product = models.ForeignKey(SQLProduct)
    sql_location = models.ForeignKey(SQLLocation, null=True)

    # override default model manager to only include unarchived data
    objects = ActiveManager()

    # leave a way to get unfiltered data
    include_archived = models.Manager()

    @property
    def months_remaining(self):
        return months_of_stock_remaining(
            self.stock_on_hand,
            self.get_daily_consumption()
        )

    @property
    def resupply_quantity_needed(self):
        monthly_consumption = self.get_monthly_consumption()
        if monthly_consumption is not None:
            stock_levels = self.get_domain().commtrack_settings.stock_levels_config
            needed_quantity = int(
                monthly_consumption * stock_levels.overstock_threshold
            )
            return int(max(needed_quantity - self.stock_on_hand, 0))
        else:
            return None

    @property
    def stock_category(self):
        return state_stock_category(self)

    @memoized
    def get_domain(self):
        return Domain.get_by_name(
            DocDomainMapping.objects.get(doc_id=self.case_id).domain_name
        )

    def get_daily_consumption(self):
        if self.daily_consumption is not None:
            return self.daily_consumption
        else:
            monthly = self._get_default_monthly_consumption()
            if monthly is not None:
                return Decimal(monthly) / Decimal(DAYS_IN_MONTH)

    def get_monthly_consumption(self):

        if self.daily_consumption is not None:
            return self.daily_consumption * Decimal(DAYS_IN_MONTH)
        else:
            return self._get_default_monthly_consumption()

    def _get_default_monthly_consumption(self):
        domain = self.get_domain()
        if domain and domain.commtrack_settings:
            config = domain.commtrack_settings.get_consumption_config()
        else:
            config = None

        return compute_default_monthly_consumption(
            self.case_id,
            self.product_id,
            config
        )

    class Meta:
        unique_together = ('section_id', 'case_id', 'product_id')


@register_column_type
class StockExportColumn(ComplexExportColumn):
    """
    A special column type for case exports. This will export a column
    for each product/section combo on the provided domain.

    See couchexport/models.
    """
    domain = StringProperty()

    @property
    @memoized
    def _column_tuples(self):
        product_ids = [p._id for p in Product.by_domain(self.domain)]
        return sorted(list(
            StockState.objects.filter(product_id__in=product_ids).values_list(
                'product_id',
                'section_id'
            ).distinct()
        ))

    def get_headers(self):
        for product_id, section in self._column_tuples:
            yield u"{product} ({section})".format(
                product=Product.get(product_id).name,
                section=section
            )

    def get_data(self, value):
        states = StockState.objects.filter(case_id=value)

        # use a list to make sure the stock states end up
        # in the same order as the headers
        values = [None] * len(self._column_tuples)

        for state in states:
            column_tuple = (state.product_id, state.section_id)
            if column_tuple in self._column_tuples:
                state_index = self._column_tuples.index(column_tuple)
                values[state_index] = state.stock_on_hand
        return values


def sync_location_supply_point(loc):
    """
    This method syncs the location/supply point connection
    and is triggered whenever a location is edited or created.
    """
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
            updated_supply_point = supply_point
        else:
            updated_supply_point = SupplyPointCase.create_from_location(loc.domain, loc)

        # need to sync this sp change to the sql location
        # but saving the doc will trigger a loop
        try:
            sql_loc = SQLLocation.objects.get(location_id=loc._id)
            sql_loc.supply_point_id = updated_supply_point._id
            sql_loc.save()
        except SQLLocation.DoesNotExist:
            pass


@receiver(post_save, sender=DbStockTransaction)
def update_stock_state_signal_catcher(sender, instance, *args, **kwargs):
    update_stock_state_for_transaction(instance)


def update_stock_state_for_transaction(instance):
    try:
        domain_name = instance.domain
    except AttributeError:
        domain_name = CommCareCase.get(instance.case_id).domain

    domain = Domain.get_by_name(domain_name)

    sql_product = SQLProduct.objects.get(product_id=instance.product_id)

    try:
        sql_location = SQLLocation.objects.get(supply_point_id=instance.case_id)
    except SQLLocation.DoesNotExist:
        sql_location = None

    try:
        state = StockState.include_archived.get(
            section_id=instance.section_id,
            case_id=instance.case_id,
            product_id=instance.product_id,
        )
    except StockState.DoesNotExist:
        state = StockState(
            section_id=instance.section_id,
            case_id=instance.case_id,
            product_id=instance.product_id,
            sql_product=sql_product,
            sql_location=sql_location,
        )

    state.last_modified_date = instance.report.date
    state.stock_on_hand = instance.stock_on_hand

    if domain and domain.commtrack_settings:
        consumption_calc = domain.commtrack_settings.get_consumption_config()
    else:
        consumption_calc = None

    state.daily_consumption = compute_daily_consumption(
        instance.case_id,
        instance.product_id,
        instance.report.date,
        'stock',
        consumption_calc
    )
    # so you don't have to look it up again in the signal receivers
    state.domain = domain
    state.save()


@receiver(post_delete, sender=DbStockTransaction)
def stock_state_deleted(sender, instance, *args, **kwargs):
    qs = DbStockTransaction.objects.filter(
        section_id=instance.section_id,
        case_id=instance.case_id,
        product_id=instance.product_id,
    ).order_by('-report__date')
    if qs:
        update_stock_state_for_transaction(qs[0])
    else:
        StockState.objects.filter(
            section_id=instance.section_id,
            case_id=instance.case_id,
            product_id=instance.product_id,
        ).delete()


@receiver(post_save, sender=StockState)
def update_domain_mapping(sender, instance, *args, **kwargs):
    case_id = unicode(instance.case_id)
    try:
        domain_name = instance.domain
        if not domain_name:
            raise ValueError()
    except (AttributeError, ValueError):
        domain_name = CommCareCase.get(case_id).domain
    if not DocDomainMapping.objects.filter(doc_id=case_id).exists():
        mapping = DocDomainMapping(
            doc_id=case_id,
            doc_type='CommCareCase',
            domain_name=domain_name,
        )
        mapping.save()


@receiver(location_edited)
def post_loc_edited(sender, loc=None, **kwargs):
    sync_location_supply_point(loc)


@receiver(location_created)
def post_loc_created(sender, loc=None, **kwargs):
    sync_location_supply_point(loc)


@receiver(xform_archived)
def remove_data(sender, xform, *args, **kwargs):
    DbStockReport.objects.filter(form_id=xform._id).delete()


@receiver(xform_unarchived)
def reprocess_form(sender, xform, *args, **kwargs):
    from corehq.apps.commtrack.processing import process_stock
    for case in process_stock(xform):
        case.save()


# import signals
from . import signals
