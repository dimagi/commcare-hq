from decimal import Decimal

from corehq.apps.consumption.const import DAYS_IN_MONTH
from corehq.apps.consumption.models import (
    TYPE_DOMAIN,
    TYPE_PRODUCT,
    TYPE_SUPPLY_POINT,
    SQLDefaultConsumption,
)


def get_default_monthly_consumption(domain, product_id, location_type, case_id):
    """
    Return the most specific consumption value for the passed
    parameters.
    """

    consumption = SQLDefaultConsumption.objects.filter(
        domain=domain,
        product_id=product_id,
        supply_point_id=case_id
    ).first()

    if not consumption:
        consumption = SQLDefaultConsumption.objects.filter(
            domain=domain,
            product_id=product_id,
            supply_point_type=location_type,
            supply_point_id=None
        ).first()

    if not consumption:
        consumption = SQLDefaultConsumption.objects.filter(
            domain=domain,
            product_id=product_id,
            supply_point_type=None,
            supply_point_id=None
        ).first()

    if not consumption:
        consumption = SQLDefaultConsumption.objects.filter(
            domain=domain,
            product_id=None,
            supply_point_type=None,
            supply_point_id=None
        ).first()

    if consumption:
        return consumption.default_consumption

    return None


def get_default_consumption(domain, product_id, location_type, case_id):
    consumption = get_default_monthly_consumption(domain, product_id, location_type, case_id)

    if consumption:
        return consumption / Decimal(DAYS_IN_MONTH)
    else:
        return None


def set_default_monthly_consumption_for_domain(domain, amount):
    default = SQLDefaultConsumption.get_domain_default(domain)
    return _update_or_create_default(domain, amount, default, TYPE_DOMAIN)


def set_default_consumption_for_product(domain, product_id, amount):
    default = SQLDefaultConsumption.get_product_default(domain, product_id)
    return _update_or_create_default(domain, amount, default, TYPE_PRODUCT, product_id=product_id)


def set_default_consumption_for_supply_point(domain, product_id, supply_point_id, amount):
    default = SQLDefaultConsumption.get_supply_point_default(domain, product_id, supply_point_id)
    return _update_or_create_default(domain, amount, default, TYPE_SUPPLY_POINT,
                                     product_id=product_id, supply_point_id=supply_point_id)


def _update_or_create_default(domain, amount, default, type, **kwargs):
    if default and default.default_consumption == amount:
        return default
    elif default:
        default.default_consumption = amount
        default.save()
        return default
    else:
        default = SQLDefaultConsumption(domain=domain, default_consumption=amount, type=type, **kwargs)
        default.save()
        return default


def build_consumption_dict(domain):
    """
    Takes raw rows from couch and builds a dict to
    look up consumption values from.
    """
    SQLDefaultConsumption.objects.filter(domain=domain)

    return dict(
        (tuple(
            obj.domain,
            obj.product_id,
            obj.supply_point_type,
            obj.supply_point_id,
        ), obj.default_consumption)
        for obj in SQLDefaultConsumption.objects.filter(domain=domain) if obj.default_consumption
    )


def get_loaded_default_monthly_consumption(consumption_dict, domain, product_id, location_type, case_id):
    """
    Recreates the couch view logic to access the most specific
    consumption value available for the passed options
    """
    keys = [
        tuple([domain, product_id, None, case_id]),
        tuple([domain, product_id, location_type, None]),
        tuple([domain, product_id, None, None]),
        tuple([domain, None, None, None]),
    ]

    for key in keys:
        if key in consumption_dict:
            return consumption_dict[key]

    return None


def get_loaded_default_consumption(consumption_dict, domain, product_id, location_type, case_id):
    consumption = get_loaded_default_monthly_consumption(consumption_dict, domain, product_id, location_type, case_id)

    if consumption:
        return consumption / Decimal(DAYS_IN_MONTH)
    else:
        return None
