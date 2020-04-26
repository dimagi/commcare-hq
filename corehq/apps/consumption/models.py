from dimagi.ext.couchdbkit import DecimalProperty, Document, StringProperty
from django.db import models

from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from dimagi.utils.couch.migration import SyncCouchToSQLMixin, SyncSQLToCouchMixin

TYPE_DOMAIN = 'domain'
TYPE_PRODUCT = 'product'
TYPE_SUPPLY_POINT_TYPE = 'supply-point-type'
TYPE_SUPPLY_POINT = 'supply-point'


class SQLDefaultConsumption(SyncSQLToCouchMixin, models.Model):
    type = models.CharField(max_length=32, null=True, choices=[
        (TYPE_DOMAIN, TYPE_DOMAIN),
        (TYPE_PRODUCT, TYPE_PRODUCT),
        (TYPE_SUPPLY_POINT_TYPE, TYPE_SUPPLY_POINT_TYPE),
        (TYPE_SUPPLY_POINT, TYPE_SUPPLY_POINT),
    ])
    domain = models.CharField(max_length=255, null=True)
    product_id = models.CharField(max_length=126, null=True)
    supply_point_type = models.CharField(max_length=126, null=True)
    supply_point_id = models.CharField(max_length=126, null=True)
    default_consumption = models.DecimalField(max_digits=64, decimal_places=8, null=True)
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta:
        db_table = "consumption_defaultconsumption"

    @classmethod
    def _migration_get_fields(cls):
        return [
            "type",
            "domain",
            "product_id",
            "supply_point_type",
            "supply_point_id",
            "default_consumption",
        ]

    @classmethod
    def _migration_get_couch_model_class(cls):
        return DefaultConsumption

    @classmethod
    def get_domain_default(cls, domain):
        return SQLDefaultConsumption.objects.filter(domain=domain).first()

    @classmethod
    def get_product_default(cls, domain, product_id):
        return SQLDefaultConsumption.objects.filter(domain=domain, product_id=product_id).first()

    @classmethod
    def get_supply_point_default(cls, domain, product_id, supply_point_id):
        return SQLDefaultConsumption.objects.filter(
            domain=domain,
            product_id=product_id,
            supply_point_id=supply_point_id,
        ).first()


class DefaultConsumption(SyncCouchToSQLMixin, CachedCouchDocumentMixin, Document):
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
    def _migration_get_fields(cls):
        return [
            "type",
            "domain",
            "product_id",
            "supply_point_type",
            "supply_point_id",
            "default_consumption",
        ]

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLDefaultConsumption
