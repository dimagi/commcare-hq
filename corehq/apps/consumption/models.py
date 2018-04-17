from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.ext.couchdbkit import Document, StringProperty, DecimalProperty
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin


TYPE_DOMAIN = 'domain'
TYPE_PRODUCT = 'product'
TYPE_SUPPLY_POINT_TYPE = 'supply-point-type'
TYPE_SUPPLY_POINT = 'supply-point'


class DefaultConsumption(CachedCouchDocumentMixin, Document):
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
        return cls._by_index_key([domain, None, None, None])

    @classmethod
    def get_product_default(cls, domain, product_id):
        return cls._by_index_key([domain, product_id, None, None])

    @classmethod
    def get_supply_point_default(cls, domain, product_id, supply_point_id):
        return cls._by_index_key([domain, product_id, {}, supply_point_id])

    @classmethod
    def _by_index_key(cls, key):
        return cls.view('consumption/consumption_index',
            key=key,
            reduce=False,
            include_docs=True,
        ).one()
