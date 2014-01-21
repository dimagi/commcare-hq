from decimal import Decimal
from corehq.apps.consumption.models import DefaultConsumption


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

