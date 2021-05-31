from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from couchdbkit.exceptions import ResourceNotFound
from memoized import memoized

from casexml.apps.case.cleanup import close_case
from casexml.apps.case.models import CommCareCase
from casexml.apps.stock.consumption import ConsumptionConfiguration
from casexml.apps.stock.models import DocDomainMapping
from couchforms.signals import xform_archived, xform_unarchived
from dimagi.ext.couchdbkit import *

from corehq.apps.consumption.shortcuts import get_default_monthly_consumption
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.form_processor.change_publishers import publish_ledger_v1_saved
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.util.quickcache import quickcache

from . import const
from .const import StockActions

STOCK_ACTION_ORDER = [
    StockActions.RECEIPTS,
    StockActions.CONSUMPTION,
    StockActions.STOCKONHAND,
    StockActions.STOCKOUT,
]


class CommtrackConfig(models.Model):
    domain = models.CharField(max_length=126, null=False, db_index=True, unique=True)

    # configured on Advanced Settings page
    use_auto_emergency_levels = models.BooleanField(default=False)

    sync_consumption_fixtures = models.BooleanField(default=False)
    use_auto_consumption = models.BooleanField(default=False)

    individual_consumption_defaults = models.BooleanField(default=False)

    @property
    def all_actions(self):
        order = self.get_actionconfig_order()
        return [ActionConfig.objects.get(id=o) for o in order]

    def set_actions(self, actions):
        self.actionconfig_set.all().delete()
        self.actionconfig_set.set(actions, bulk=False)
        self.set_actionconfig_order([a.id for a in actions])

    def action_by_keyword(self, keyword):
        return {a.keyword.lower(): a for a in self.all_actions}.get(keyword.lower())

    @classmethod
    def for_domain(cls, domain):
        return cls.objects.filter(domain=domain).first()

    def get_consumption_config(self):
        def _default_monthly_consumption(case_id, product_id):
            # note: for now as an optimization hack, per-supply point type is not supported
            # unless explicitly configured, because it will require looking up the case
            facility_type = None
            if self.consumptionconfig.use_supply_point_type_default_consumption:
                try:
                    supply_point = SupplyInterface(self.domain).get_supply_point(case_id)
                    facility_type = supply_point.sql_location.location_type_name
                except ResourceNotFound:
                    pass
            return get_default_monthly_consumption(self.domain, product_id, facility_type, case_id)

        return ConsumptionConfiguration(
            min_periods=self.consumptionconfig.min_transactions,
            min_window=self.consumptionconfig.min_window,
            max_window=self.consumptionconfig.optimal_window,
            default_monthly_consumption_function=_default_monthly_consumption,
            exclude_invalid_periods=self.consumptionconfig.exclude_invalid_periods
        )

    def get_ota_restore_settings(self):
        # for some reason it doesn't like this import
        from casexml.apps.phone.restore import StockSettings
        default_product_ids = []
        if self.stockrestoreconfig.use_dynamic_product_list:
            default_product_ids = SQLProduct.active_objects.filter(domain=self.domain).product_ids()

        def case_filter(stub):
            return stub.type in set(self.stockrestoreconfig.force_consumption_case_types)

        return StockSettings(
            section_to_consumption_types=self.stockrestoreconfig.section_to_consumption_types,
            consumption_config=self.get_consumption_config(),
            default_product_list=default_product_ids,
            force_consumption_case_filter=case_filter,
            sync_consumption_ledger=self.sync_consumption_fixtures
        )

    def to_json(self):
        config = {
            "domain": self.domain,
            "actions": [a.to_json() for a in self.all_actions],
            "use_auto_emergency_levels": self.use_auto_emergency_levels,
            "sync_consumption_fixtures": self.sync_consumption_fixtures,
            "use_auto_consumption": self.use_auto_consumption,
            "individual_consumption_defaults": self.individual_consumption_defaults,
        }
        for json_attr, sql_attr in {
            'alert_config': 'alertconfig',
            'consumption_config': 'consumptionconfig',
            'ota_restore_config': 'stockrestoreconfig',
            'stock_levels_config': 'stocklevelsconfig',
        }.items():
            if hasattr(self, sql_attr):
                config[json_attr] = getattr(self, sql_attr).to_json()
            else:
                config[json_attr] = {}
        return config


# supported stock actions for this commtrack domain
# listed in the order they are processed -- TODO support for this custom ordering might go away
# TODO must catch ambiguous action lists (two action configs with the same 'name')
class ActionConfig(models.Model):
    # one of the base stock action types (see StockActions enum)
    action = models.CharField(max_length=40, null=True)
    # (optional) to further distinguish different kinds of the base action
    # (i.e., separately tracking consumption as 'dispensed' or 'lost'). note that when the system
    # infers consumption/receipts from reported stock, it will be marked here as a subaction
    subaction = models.CharField(max_length=40, null=True)
    # sms code
    _keyword = models.CharField(max_length=40, null=True)
    # display title
    caption = models.CharField(max_length=40, null=True)

    commtrack_config = models.ForeignKey('CommtrackConfig', on_delete=models.CASCADE)

    class Meta:
        order_with_respect_to = "commtrack_config"

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

    def __repr__(self):
        return '{action} ({subaction}): {caption} ({_keyword})'.format(
            action=self.action,
            subaction=self.subaction,
            caption=self.caption,
            _keyword=self._keyword,
        )

    def to_json(self):
        return {
            'action': self.action,
            'subaction': self.subaction,
            '_keyword': self._keyword,
            'caption': self.caption,
        }


class ConsumptionConfig(models.Model):
    min_transactions = models.IntegerField(default=2, null=True)
    min_window = models.IntegerField(default=10, null=True)
    optimal_window = models.IntegerField(null=True)
    use_supply_point_type_default_consumption = models.BooleanField(default=False)
    exclude_invalid_periods = models.BooleanField(default=False)

    commtrack_config = models.OneToOneField(
        CommtrackConfig,
        on_delete=models.CASCADE,
        primary_key=True,
    )

    def to_json(self):
        return {
            "min_transactions": self.min_transactions,
            "min_window": self.min_window,
            "optimal_window": self.optimal_window,
            "use_supply_point_type_default_consumption": self.use_supply_point_type_default_consumption,
            "exclude_invalid_periods": self.exclude_invalid_periods,
        }


class StockLevelsConfig(models.Model):
    # All of these are in months
    emergency_level = models.DecimalField(default=0.5, max_digits=4, decimal_places=2)
    understock_threshold = models.DecimalField(default=1.5, max_digits=4, decimal_places=2)
    overstock_threshold = models.DecimalField(default=3, max_digits=5, decimal_places=2)

    commtrack_config = models.OneToOneField(
        CommtrackConfig,
        on_delete=models.CASCADE,
        primary_key=True,
    )

    def to_json(self):
        return {
            "emergency_level": self.emergency_level,
            "understock_threshold": self.understock_threshold,
            "overstock_threshold": self.overstock_threshold,
        }


# configured on Subscribe SMS page
class AlertConfig(models.Model):
    stock_out_facilities = models.BooleanField(default=False)
    stock_out_commodities = models.BooleanField(default=False)
    stock_out_rates = models.BooleanField(default=False)
    non_report = models.BooleanField(default=False)

    commtrack_config = models.OneToOneField(
        CommtrackConfig,
        on_delete=models.CASCADE,
        primary_key=True,
    )

    def to_json(self):
        return {
            "stock_out_facilities": self.stock_out_facilities,
            "stock_out_commodities": self.stock_out_commodities,
            "stock_out_rates": self.stock_out_rates,
            "non_report": self.non_report,
        }


class StockRestoreConfig(models.Model):
    section_to_consumption_types = JSONField(default=dict, null=True)
    force_consumption_case_types = JSONField(default=list, null=True)
    use_dynamic_product_list = models.BooleanField(default=False)

    commtrack_config = models.OneToOneField(
        CommtrackConfig,
        on_delete=models.CASCADE,
        primary_key=True,
    )

    def to_json(self):
        return {
            "section_to_consumption_types": self.section_to_consumption_types,
            "force_consumption_case_types": self.force_consumption_case_types,
            "use_dynamic_product_list": self.use_dynamic_product_list,
        }


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
    def last_modified(self):
        return self.last_modified_date

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
        from corehq.apps.reports.commtrack.util import get_consumption_helper_from_ledger_value
        return get_consumption_helper_from_ledger_value(self.domain, self)

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
    case_id = str(instance.case_id)
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
