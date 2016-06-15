from decimal import Decimal

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from couchdbkit.exceptions import ResourceNotFound

from corehq.form_processor.change_publishers import publish_ledger_v1_saved
from dimagi.ext.couchdbkit import *
from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.cleanup import close_case
from casexml.apps.case.models import CommCareCase
from casexml.apps.stock.consumption import (ConsumptionConfiguration, compute_default_monthly_consumption)
from casexml.apps.stock.models import DocDomainMapping
from casexml.apps.stock.utils import months_of_stock_remaining, state_stock_category
from couchexport.models import register_column_type, ComplexExportColumn
from couchforms.signals import xform_archived, xform_unarchived
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.apps.consumption.shortcuts import get_default_monthly_consumption
from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
from corehq.apps.domain.models import Domain
from corehq.apps.domain.signals import commcare_domain_pre_delete
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.products.models import Product, SQLProduct
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.util.quickcache import quickcache
from . import const
from .const import StockActions, RequisitionActions, DAYS_IN_MONTH


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
    exclude_invalid_periods = BooleanProperty(default=False)


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


class CommtrackConfig(QuickCachedDocumentMixin, Document):
    domain = StringProperty()

    # supported stock actions for this commtrack domain
    # listed in the order they are processed -- TODO support for this custom ordering might go away
    actions = SchemaListProperty(CommtrackActionConfig)
    # TODO must catch ambiguous action lists (two action configs with the same 'name')

    multiaction_enabled = BooleanProperty()
    multiaction_keyword_ = StringProperty()

    requisition_config = SchemaProperty(CommtrackRequisitionConfig)
    openlmis_config = SchemaProperty(OpenLMISConfig)

    # configured on Advanced Settings page
    use_auto_emergency_levels = BooleanProperty(default=False)

    sync_consumption_fixtures = BooleanProperty(default=False)
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

    def clear_caches(self):
        super(CommtrackConfig, self).clear_caches()
        self.for_domain.clear(self.__class__, self.domain)

    @classmethod
    @quickcache(vary_on=['domain'])
    def for_domain(cls, domain):
        result = get_docs_in_domain_by_class(domain, cls)
        try:
            return result[0]
        except IndexError:
            return None

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
                    supply_point = SupplyInterface(self.domain).get_supply_point(case_id)
                    facility_type = supply_point.sql_location.location_type_name
                except ResourceNotFound:
                    pass
            return get_default_monthly_consumption(self.domain, product_id, facility_type, case_id)

        return ConsumptionConfiguration(
            min_periods=self.consumption_config.min_transactions,
            min_window=self.consumption_config.min_window,
            max_window=self.consumption_config.optimal_window,
            default_monthly_consumption_function=_default_monthly_consumption,
            exclude_invalid_periods=self.consumption_config.exclude_invalid_periods
        )

    def get_ota_restore_settings(self):
        # for some reason it doesn't like this import
        from casexml.apps.phone.restore import StockSettings
        default_product_ids = Product.ids_by_domain(self.domain) \
            if self.ota_restore_config.use_dynamic_product_list else []
        case_filter = lambda stub: stub.type in set(self.ota_restore_config.force_consumption_case_types)
        return StockSettings(
            section_to_consumption_types=self.ota_restore_config.section_to_consumption_types,
            consumption_config=self.get_consumption_config(),
            default_product_list=default_product_ids,
            force_consumption_case_filter=case_filter,
            sync_consumption_ledger=self.sync_consumption_fixtures
        )

    @property
    def requisitions_enabled(self):
        return self.requisition_config.enabled

    @property
    def openlmis_enabled(self):
        return self.openlmis_config.enabled


@receiver(commcare_domain_pre_delete)
def clear_commtrack_config_cache(domain, **kwargs):
    config = CommtrackConfig.for_domain(domain.name)
    if config:
        config.delete()


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


class SupplyPointCase(CommCareCase):
    """
    A wrapper around CommCareCases to get more built in functionality
    specific to supply points.
    """
    location_id = StringProperty()

    class Meta:
        # This is necessary otherwise couchdbkit will confuse this app with casexml
        app_label = "commtrack"

    @property
    @memoized
    def location(self):
        if self.location_id is None:
            return None
        try:
            return Location.get(self.location_id)
        except ResourceNotFound:
            return None

    @property
    def sql_location(self):
        return SQLLocation.objects.get(location_id=self.location_id)


UNDERSTOCK_THRESHOLD = 0.5  # months
OVERSTOCK_THRESHOLD = 2.  # months
DEFAULT_CONSUMPTION = 10.  # per month


class ActiveManager(models.Manager):
    """
    Filter any object that is associated to an archived product
    """

    def get_queryset(self):
        return super(ActiveManager, self).get_queryset() \
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
    last_modified_form_id = models.CharField(max_length=100, null=True)
    sql_product = models.ForeignKey(SQLProduct)
    sql_location = models.ForeignKey(SQLLocation, null=True)

    # override default model manager to only include unarchived data
    objects = ActiveManager()

    # leave a way to get unfiltered data
    include_archived = models.Manager()

    @property
    def entry_id(self):
        return self.product_id

    @property
    def balance(self):
        return self.stock_on_hand

    @property
    def months_remaining(self):
        return months_of_stock_remaining(
            self.stock_on_hand,
            self.get_daily_consumption()
        )

    @property
    def resupply_quantity_needed(self):
        monthly_consumption = self.get_monthly_consumption()
        if monthly_consumption is not None and self.sql_location is not None:
            overstock = self.sql_location.location_type.overstock_threshold
            needed_quantity = int(
                monthly_consumption * overstock
            )
            return int(max(needed_quantity - self.stock_on_hand, 0))
        else:
            return None

    @property
    def stock_category(self):
        return state_stock_category(self)

    @property
    @memoized
    def domain(self):
        try:
            domain_name = self.__domain
            if domain_name:
                return domain_name
        except AttributeError:
            pass

        try:
            return DocDomainMapping.objects.get(doc_id=self.case_id).domain_name
        except DocDomainMapping.DoesNotExist:
            return CommCareCase.get(self.case_id).domain

    @memoized
    def get_domain(self):
        return Domain.get_by_name(self.domain)

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

    def to_json(self):
        from corehq.form_processor.serializers import StockStateSerializer
        serializer = StockStateSerializer(self)
        return serializer.data

    class Meta:
        app_label = 'commtrack'
        unique_together = ('section_id', 'case_id', 'product_id')


@register_column_type()
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


def _make_location_admininstrative(location):
    supply_point_id = location.supply_point_id
    if supply_point_id:
        close_case(supply_point_id, location.domain, const.COMMTRACK_USERNAME)
    location.supply_point_id = None  # this will be saved soon anyways


def _reopen_or_create_supply_point(location):
    from .helpers import update_supply_point_from_location
    supply_point = SupplyInterface(location.domain).get_closed_and_open_by_location_id_and_domain(
        location.domain,
        location.location_id
    )
    if supply_point:
        if supply_point and supply_point.closed:
            transactions = supply_point.get_closing_transactions()
            for transaction in transactions:
                transaction.form.archive(user_id=const.COMMTRACK_USERNAME)

        update_supply_point_from_location(supply_point, location)
        return supply_point
    else:
        return SupplyInterface.create_from_location(location.domain, location)


def sync_supply_point(location):
    # Called on location.save()
    domain = Domain.get_by_name(location.domain)
    if not domain.commtrack_enabled:
        return None

    if location.location_type.administrative:
        _make_location_admininstrative(location)
        return None
    else:
        updated_supply_point = _reopen_or_create_supply_point(location)
        return updated_supply_point.case_id


@receiver(post_save, sender=StockState)
def update_domain_mapping(sender, instance, *args, **kwargs):
    case_id = unicode(instance.case_id)
    try:
        domain_name = instance.__domain
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


@receiver(post_save, sender=StockState)
def publish_stock_state_to_kafka(sender, instance, *args, **kwargs):
    publish_ledger_v1_saved(instance)


@receiver(xform_archived)
def remove_data(sender, xform, *args, **kwargs):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    FormProcessorInterface(xform.domain).ledger_processor.process_form_archived(xform)


@receiver(xform_unarchived)
def reprocess_form(sender, xform, *args, **kwargs):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    FormProcessorInterface(xform.domain).ledger_processor.process_form_unarchived(xform)
