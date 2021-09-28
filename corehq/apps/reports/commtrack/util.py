from casexml.apps.stock.consumption import ConsumptionHelper

from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.util.quickcache import quickcache


def get_consumption_helper_from_ledger_value(domain, ledger_value):
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
