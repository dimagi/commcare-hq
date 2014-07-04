import logging
from corehq import Domain
from corehq.apps.users.models import WebUser
from custom.api.utils import apply_updates
from custom.ilsgateway.api import ILSGatewayEndpoint
from corehq.apps.commtrack.models import Product
from dimagi.utils.dates import force_to_datetime


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
        if apply_updates(product, product_dict):
            product.save()
    return product


def sync_ilsgateway_webusers(domain, ilsgateway_webuser):


    user = WebUser.get_by_username(ilsgateway_webuser.email.lower())
    user_dict = {
        'domain': domain.name,
        'username': ilsgateway_webuser.email.lower(),
        'first_name': ilsgateway_webuser.first_name,
        'last_name': ilsgateway_webuser.last_name,
        'email': ilsgateway_webuser.email,
        'password': ilsgateway_webuser.password,
        'is_staff': ilsgateway_webuser.is_staff,
        'is_active': ilsgateway_webuser.is_active,
        'is_superuser': ilsgateway_webuser.is_superuser,
        'last_login': force_to_datetime(ilsgateway_webuser.last_login),
        'date_joined': force_to_datetime(ilsgateway_webuser.date_joined),
        #TODO Location and supply point
        #'location': ilsgateway_webuser.location,
        #'supply_point': ilsgateway_webuser.supply_point,
        'is_ilsuser': True,
        'role_id': ilsgateway_webuser.role_id if hasattr(ilsgateway_webuser, 'role_id') else None
    }

    if user is None:
        try:
            user = WebUser.create(**user_dict)
        except Exception as e:
            logging.error(e)
    else:
        if domain.name not in user.get_domains():
            role_id = user_dict.get('role_id', None)
            user.add_domain_membership(domain.name, role_id=role_id)
            user.save()

    return user


def bootstrap_domain(domain):
    project = Domain.get_by_name(domain)
    if project.commtrack_settings and project.commtrack_settings.ilsgateway_config.is_configured:
        endpoint = ILSGatewayEndpoint.from_config(project.commtrack_settings.ilsgateway_config)
        for product in endpoint.get_products():
            sync_ilsgateway_product(domain, product)