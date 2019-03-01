from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.exceptions import ObjectDoesNotExist
from casexml.apps.stock.consumption import ConsumptionHelper
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.util.quickcache import quickcache
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

    @property
    @quickcache(['self.domain', 'self.entry_id'])
    def sql_product(self):
        try:
            return SQLProduct.objects.get(domain=self.domain, product_id=self.entry_id)
        except ObjectDoesNotExist:
            return None

    @property
    @quickcache(['self.domain', 'self.location_id'])
    def sql_location(self):
        try:
            return (
                SQLLocation.objects
                .select_related('location_type')
                .get(domain=self.domain, location_id=self.location_id)
            )
        except ObjectDoesNotExist:
            return None

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


@quickcache(['domain', 'program_id'])
def get_product_id_name_mapping(domain, program_id=None):
    products = SQLProduct.objects.filter(domain=domain)
    if program_id:
        products = products.filter(program_id=program_id)
    return dict(products.values_list('product_id', 'name'))


def get_product_ids_for_program(domain, program_id):
    qs = SQLProduct.objects.filter(
        domain=domain, program_id=program_id
    ).values_list('product_id', flat=True)
    return list(qs)
