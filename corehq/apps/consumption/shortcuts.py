from decimal import Decimal
from corehq.apps.consumption.models import DefaultConsumption, TYPE_DOMAIN, TYPE_PRODUCT, TYPE_SUPPLY_POINT


def get_default_consumption(domain, product_id, location_type, case_id):
    keys = [
        [domain, product_id, {}, case_id],
        [domain, product_id, location_type, None],
        [domain, product_id, None, None],
        [domain, None, None, None],
    ]
    results = DefaultConsumption.get_db().view(
        'consumption/consumption_index',
        keys=keys, reduce=False, limit=1, descending=True,
    )
    results = results.one()
    return Decimal(results['value']) if results else None


def set_default_consumption_for_domain(domain, amount):
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
