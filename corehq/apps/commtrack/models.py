from __future__ import absolute_import
from __future__ import unicode_literals
from decimal import Decimal

from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from couchdbkit.exceptions import ResourceNotFound

from corehq.form_processor.change_publishers import publish_ledger_v1_saved
from dimagi.ext.couchdbkit import *
from memoized import memoized

from casexml.apps.case.cleanup import close_case
from casexml.apps.case.models import CommCareCase
from casexml.apps.stock.consumption import ConsumptionConfiguration, ConsumptionHelper
from casexml.apps.stock.models import DocDomainMapping
from couchforms.signals import xform_archived, xform_unarchived
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.apps.consumption.shortcuts import get_default_monthly_consumption
from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
from corehq.apps.domain.models import Domain
from corehq.apps.domain.signals import commcare_domain_pre_delete
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import Product, SQLProduct
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.util.quickcache import quickcache
from . import const
from .const import StockActions
import six
from six.moves import filter


STOCK_ACTION_ORDER = [
    StockActions.RECEIPTS,
    StockActions.CONSUMPTION,
    StockActions.STOCKONHAND,
    StockActions.STOCKOUT,
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

    # configured on Advanced Settings page
    use_auto_emergency_levels = BooleanProperty(default=False)

    sync_consumption_fixtures = BooleanProperty(default=False)
    use_auto_consumption = BooleanProperty(default=False)
    consumption_config = SchemaProperty(ConsumptionConfig)
    stock_levels_config = SchemaProperty(StockLevelsConfig)
    ota_restore_config = SchemaProperty(StockRestoreConfig)
    individual_consumption_defaults = BooleanProperty(default=False)

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
        return self.actions

    def action_by_keyword(self, keyword):
        return dict((a.keyword.lower(), a) for a in self.actions).get(keyword.lower())

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

    class Meta(object):
        # This is necessary otherwise couchdbkit will confuse this app with casexml
        app_label = "commtrack"

    @property
    @memoized
    def sql_location(self):
        return SQLLocation.objects.get(location_id=self.location_id)

    location = sql_location


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
    sql_product = models.ForeignKey(SQLProduct, on_delete=models.CASCADE)
    sql_location = models.ForeignKey(SQLLocation, null=True, on_delete=models.CASCADE)

    # override default model manager to only include unarchived data
    objects = ActiveManager()

    # leave a way to get unfiltered data
    include_archived = models.Manager()

    @property
    def entry_id(self):
        return self.product_id

    @property
    def location_id(self):
        return self.sql_location.location_id if self.sql_location else None

    @property
    def balance(self):
        return self.stock_on_hand

    @property
    def ledger_reference(self):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        return UniqueLedgerReference(
            case_id=self.case_id, section_id=self.section_id, entry_id=self.product_id
        )

    @property
    @memoized
    def consumption_helper(self):
        return ConsumptionHelper(
            domain=self.get_domain(),
            case_id=self.case_id,
            section_id=self.section_id,
            entry_id=self.product_id,
            daily_consumption=self.daily_consumption,
            balance=self.balance,
            sql_location=self.sql_location,
        )

    @property
    def months_remaining(self):
        return self.consumption_helper.get_months_remaining()

    @property
    def resupply_quantity_needed(self):
        return self.consumption_helper.get_resupply_quantity_needed()

    @property
    def stock_category(self):
        return self.consumption_helper.get_stock_category()

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
        return self.consumption_helper.get_daily_consumption()

    def get_monthly_consumption(self):
        return self.consumption_helper.get_monthly_consumption()

    def to_json(self):
        from corehq.form_processor.serializers import StockStateSerializer
        serializer = StockStateSerializer(self)
        return dict(serializer.data)

    class Meta(object):
        app_label = 'commtrack'
        unique_together = ('section_id', 'case_id', 'product_id')


def close_supply_point_case(domain, supply_point_id):
    if supply_point_id:
        close_case(
            supply_point_id,
            domain,
            const.COMMTRACK_USERNAME,
            __name__ + ".close_supply_point_case",
        )


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


def sync_supply_point(location, is_deletion=False):
    """Called on location save() or delete().  Updates the supply_point_id if appropriate"""
    domain_obj = Domain.get_by_name(location.domain)
    if not domain_obj.commtrack_enabled:
        return None

    if location.location_type.administrative or is_deletion:
        close_supply_point_case(location.domain, location.supply_point_id)
        location.supply_point_id = None
    elif location.is_archived:
        close_supply_point_case(location.domain, location.supply_point_id)
    else:
        updated_supply_point = _reopen_or_create_supply_point(location)
        location.supply_point_id = updated_supply_point.case_id


@receiver(post_save, sender=StockState)
def update_domain_mapping(sender, instance, *args, **kwargs):
    case_id = six.text_type(instance.case_id)
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
def publish_stock_state_to_kafka_on_save(sender, instance, *args, **kwargs):
    publish_ledger_v1_saved(instance)


@receiver(post_delete, sender=StockState)
def publish_stock_state_to_kafka_on_delete(sender, instance, *args, **kwargs):
    publish_ledger_v1_saved(instance, deleted=True)


@receiver(xform_archived)
def remove_data(sender, xform, *args, **kwargs):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    FormProcessorInterface(xform.domain).ledger_processor.process_form_archived(xform)


@receiver(xform_unarchived)
def reprocess_form(sender, xform, *args, **kwargs):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    FormProcessorInterface(xform.domain).ledger_processor.process_form_unarchived(xform)
