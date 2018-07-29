from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from decimal import Decimal
from corehq.apps.consumption.models import DefaultConsumption, TYPE_DOMAIN, TYPE_PRODUCT, TYPE_SUPPLY_POINT
from corehq.apps.consumption.const import DAYS_IN_MONTH
from dimagi.utils.couch.cache import cache_core


def get_default_monthly_consumption(domain, product_id, location_type, case_id):
    """
    Return the most specific consumption value for the passed
    parameters.
    """

    keys = [
        [domain, product_id, {}, case_id],
        [domain, product_id, location_type, None],
        [domain, product_id, None, None],
        [domain, None, None, None],
    ]

    results = cache_core.cached_view(
        DefaultConsumption.get_db(),
        'consumption/consumption_index',
        keys=keys,
        reduce=False,
        limit=1,
    )
    results = results[0] if results else None
    if results and results['value']:
        return Decimal(results['value'])
    else:
        return None


def get_domain_monthly_consumption_data(domain):
    """
    Get all default consumption rows for this domain.
    """
    results = cache_core.cached_view(
        DefaultConsumption.get_db(),
        'consumption/consumption_index',
        startkey=[domain],
        endkey=[domain, {}],
        reduce=False,
    )
    return results


def get_default_consumption(domain, product_id, location_type, case_id):
    consumption = get_default_monthly_consumption(domain, product_id, location_type, case_id)

    if consumption:
        return consumption / Decimal(DAYS_IN_MONTH)
    else:
        return None


def set_default_monthly_consumption_for_domain(domain, amount):
    default = DefaultConsumption.get_domain_default(domain)
    return _update_or_create_default(domain, amount, default, TYPE_DOMAIN)


def set_default_consumption_for_product(domain, product_id, amount):
    default = DefaultConsumption.get_product_default(domain, product_id)
    return _update_or_create_default(domain, amount, default, TYPE_PRODUCT, product_id=product_id)


def set_default_consumption_for_supply_point(domain, product_id, supply_point_id, amount):
    default = DefaultConsumption.get_supply_point_default(domain, product_id, supply_point_id)
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
        default = DefaultConsumption(domain=domain, default_consumption=amount, type=type, **kwargs)
        default.save()
        return default


def hashable_key(key):
    """
    Convert the key from couch into something hasable.
    Mostly, just need to make it a tuple and remove the special
    {} value.
    """
    return tuple('{}' if item == {} else item for item in key)


def build_consumption_dict(domain):
    """
    Takes raw rows from couch and builds a dict to 
    look up consumption values from.
    """
    raw_rows = get_domain_monthly_consumption_data(domain)

    return dict(
        (hashable_key(row['key']), Decimal(row['value']))
        for row in raw_rows if row['value']
    )


def get_loaded_default_monthly_consumption(consumption_dict, domain, product_id, location_type, case_id):
    """
    Recreates the couch view logic to access the most specific
    consumption value available for the passed options
    """
    keys = [
        tuple([domain, product_id, '{}', case_id]),
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
