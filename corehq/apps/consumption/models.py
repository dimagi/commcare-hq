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

    @classmethod
    def get_domain_default(cls, domain):
        return cls.view('consumption/consumption_index',
            key=[domain, None, None, None],
            reduce=False,
            include_docs=True,
        ).one()