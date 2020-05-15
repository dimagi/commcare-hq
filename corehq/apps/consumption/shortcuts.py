from decimal import Decimal

from corehq.apps.consumption.models import (
    TYPE_DOMAIN,
    TYPE_PRODUCT,
    TYPE_SUPPLY_POINT,
    DefaultConsumption,
)


def get_default_monthly_consumption(domain, product_id, location_type, case_id):
    """
    Return the most specific consumption value for the passed
    parameters.
    """

    consumption = DefaultConsumption.objects.filter(
        domain=domain,
        product_id=product_id,
        supply_point_id=case_id
    ).first()

    if not consumption:
        consumption = DefaultConsumption.objects.filter(
            domain=domain,
            product_id=product_id,
            supply_point_type=location_type,
            supply_point_id=None
        ).first()

    if not consumption:
        consumption = DefaultConsumption.objects.filter(
            domain=domain,
            product_id=product_id,
            supply_point_type=None,
            supply_point_id=None
        ).first()

    if not consumption:
        consumption = DefaultConsumption.objects.filter(
            domain=domain,
            product_id=None,
            supply_point_type=None,
            supply_point_id=None
        ).first()

    if consumption:
        return consumption.default_consumption

    return None


def set_default_monthly_consumption_for_domain(domain, amount):
    default = DefaultConsumption.get_domain_default(domain)
    return _update_or_create_default(domain, amount, default, TYPE_DOMAIN)


def set_default_consumption_for_product(domain, product_id, amount):
    default = DefaultConsumption.get_product_default(domain, product_id)
    return _update_or_create_default(domain, amount, default, TYPE_PRODUCT, product_id=product_id)


def _update_or_create_default(domain, amount, default, type, **kwargs):
    if default and default.default_consumption == amount:
        return default
    elif default:
        default.default_consumption = amount
        default.save()
        return default
    else:
        default = DefaultConsumption(domain=domain, default_consumption=amount, type=type, **kwargs)
        default.save()
        return default


def build_consumption_dict(domain):
    """
    Builds a dict to look up consumption values from.
    """
    return {
        _hash_key(obj): obj.default_consumption
        for obj in DefaultConsumption.objects.filter(domain=domain)
        if obj.default_consumption
    }


def _hash_key(default_consumption):
    return (
        default_consumption.domain,
        default_consumption.product_id,
        default_consumption.supply_point_type,
        default_consumption.supply_point_id,
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
