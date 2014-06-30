import logging
from corehq import Domain
from custom import _apply_updates
from custom.ilsgateway.api import ILSGatewayEndpoint
from corehq.apps.commtrack.models import Product

def sync_ilsgateway_product(domain, ilsgateway_product):
    product = Product.get_by_code(domain, ilsgateway_product.sms_code)
    product_dict = {
        'domain': domain,
        'name':  ilsgateway_product.name,
        'code':  ilsgateway_product.sms_code,
        'unit': str(ilsgateway_product.units),
        'description': ilsgateway_product.description,
    }
    if product is None:
        product = Product(**product_dict)
        product.save()
    else:
        if _apply_updates(product, product_dict):
            product.save()
    return product


def bootstrap_domain(domain):
    project = Domain.get_by_name(domain)
    if project.commtrack_settings and project.commtrack_settings.ilsgateway_config.is_configured:
        endpoint = ILSGatewayEndpoint.from_config(project.commtrack_settings.ilsgateway_config)
        for product in endpoint.get_products():
            sync_ilsgateway_product(domain, product)