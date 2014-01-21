from decimal import Decimal
from corehq.apps.consumption.models import DefaultConsumption, TYPE_DOMAIN


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
    if default and default.default_consumption == amount:
        return default
    elif default:
        default.default_consumption = amount
        default.save()
        return default
    else:
        default = DefaultConsumption(domain=domain, default_consumption=amount, type=TYPE_DOMAIN)
        default.save()
        return default
