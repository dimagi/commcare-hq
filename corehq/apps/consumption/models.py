from django.db import models

TYPE_DOMAIN = 'domain'
TYPE_PRODUCT = 'product'
TYPE_SUPPLY_POINT_TYPE = 'supply-point-type'
TYPE_SUPPLY_POINT = 'supply-point'


class DefaultConsumption(models.Model):
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

    @classmethod
    def get_domain_default(cls, domain):
        return DefaultConsumption.objects.filter(domain=domain).first()

    @classmethod
    def get_product_default(cls, domain, product_id):
        return DefaultConsumption.objects.filter(domain=domain, product_id=product_id).first()

    @classmethod
    def get_supply_point_default(cls, domain, product_id, supply_point_id):
        return DefaultConsumption.objects.filter(
            domain=domain,
            product_id=product_id,
            supply_point_id=supply_point_id,
        ).first()
