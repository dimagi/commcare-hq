from django.db import models
from django.dispatch import receiver

from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case.cleanup import close_case
from casexml.apps.stock.consumption import ConsumptionConfiguration
from couchforms.signals import xform_archived, xform_unarchived

from corehq.apps.consumption.shortcuts import get_default_monthly_consumption
from corehq.apps.domain.models import Domain
from corehq.apps.products.models import SQLProduct
from corehq.form_processor.interfaces.supply import SupplyInterface

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
    section_to_consumption_types = models.JSONField(default=dict, null=True)
    force_consumption_case_types = models.JSONField(default=list, null=True)
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


def sync_supply_point(location, is_deletion=False, update_fields=None):
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

    if update_fields:
        update_fields.append('supply_point_id')


@receiver(xform_archived)
def remove_data(sender, xform, *args, **kwargs):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    FormProcessorInterface(xform.domain).ledger_processor.process_form_archived(xform)


@receiver(xform_unarchived)
def reprocess_form(sender, xform, *args, **kwargs):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    FormProcessorInterface(xform.domain).ledger_processor.process_form_unarchived(xform)
