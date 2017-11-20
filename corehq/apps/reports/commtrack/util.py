from __future__ import absolute_import
from django.core.exceptions import ObjectDoesNotExist
from casexml.apps.stock.consumption import ConsumptionHelper
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from dimagi.ext import jsonobject


class StockLedgerValueWrapper(jsonobject.JsonObject):
    """
    Wrapper class to abstract StockState and the equivalent model coming out of Elasticsearch
    """
    domain = jsonobject.StringProperty()
    case_id = jsonobject.StringProperty()
    section_id = jsonobject.StringProperty()
    entry_id = jsonobject.StringProperty()
    balance = jsonobject.DecimalProperty()  # todo: should this be an int?
    last_modified = jsonobject.DateTimeProperty()
    last_modified_form_id = jsonobject.StringProperty()
    daily_consumption = jsonobject.FloatProperty()
    location_id = jsonobject.StringProperty()

    _sql_product = None
    _sql_location = None

    def __init__(self, _obj=None, sql_product=None, sql_location=None, *args, **kwargs):
        self._sql_product = sql_product
        self._sql_location = sql_location
        super(StockLedgerValueWrapper, self).__init__(_obj, *args, **kwargs)

    @property
    def sql_product(self):
        if self.entry_id and not self._sql_product:
            try:
                self._sql_product = SQLProduct.objects.get(domain=self.domain, product_id=self.entry_id)
            except ObjectDoesNotExist:
                # todo: cache this result so multiple failing calls don't keep hitting the DB
                return None

        return self._sql_product

    @property
    def sql_location(self):
        if self.location_id and not self._sql_location:
            try:
                self._sql_location = SQLLocation.objects.get(domain=self.domain, location_id=self.location_id)
            except ObjectDoesNotExist:
                # todo: cache this result so multiple failing calls don't keep hitting the DB
                return None

        return self._sql_location

    @classmethod
    def from_stock_state(cls, stock_state):
        return cls(
            case_id=stock_state.case_id,
            section_id=stock_state.section_id,
            entry_id=stock_state.product_id,
            balance=stock_state.stock_on_hand,
            last_modified=stock_state.last_modified_date,
            last_modified_form_id=stock_state.last_modified_form_id,
            daily_consumption=stock_state.daily_consumption,
            location_id=stock_state.location_id,
            sql_location=stock_state.sql_location,
            sql_product=stock_state.sql_product,
        )


def get_consumption_helper_from_ledger_value(domain, ledger_value):
    assert isinstance(ledger_value, StockLedgerValueWrapper)
    return ConsumptionHelper(
        domain=domain,
        case_id=ledger_value.case_id,
        section_id=ledger_value.section_id,
        entry_id=ledger_value.entry_id,
        daily_consumption=ledger_value.daily_consumption,
        balance=ledger_value.balance,
        sql_location=ledger_value.sql_location,
    )


def get_relevant_supply_point_ids(domain, active_sql_location=None):
    """
    Return a list of supply point ids for the selected location
    and all of its descendants OR all supply point ids in the domain.
    """
    def filter_relevant(queryset):
        return queryset.filter(
            supply_point_id__isnull=False
        ).values_list(
            'supply_point_id',
            flat=True
        )

    if active_sql_location:
        supply_point_ids = []
        if active_sql_location.supply_point_id:
            supply_point_ids.append(active_sql_location.supply_point_id)
        supply_point_ids += list(
            filter_relevant(active_sql_location.get_descendants())
        )

        return supply_point_ids
    else:
        return list(filter_relevant(SQLLocation.objects.filter(domain=domain)))


def get_product_id_name_mapping(domain):
    return dict(SQLProduct.objects.filter(domain=domain).values_list('product_id', 'name'))


def get_product_ids_for_program(domain, program_id):
    qs = SQLProduct.objects.filter(
        domain=domain, program_id=program_id
    ).values_list('product_id', flat=True)
    return list(qs)
