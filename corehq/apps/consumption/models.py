from decimal import Decimal
from couchdbkit.ext.django.schema import Document, StringProperty, DecimalProperty


TYPE_DOMAIN = 'domain'
TYPE_PRODUCT = 'product'
TYPE_SUPPLY_POINT_TYPE = 'supply-point-type'
TYPE_SUPPLY_POINT = 'supply-point'

class DefaultConsumption(Document):
    """
    Model for setting the default consumption value of an entity
    """
    type = StringProperty()  # 'domain', 'product', 'supply-point-type', 'supply-point'
    domain = StringProperty()
    product_id = StringProperty()
    supply_point_type = StringProperty()
    supply_point_id = StringProperty()
    default_consumption = DecimalProperty()


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
