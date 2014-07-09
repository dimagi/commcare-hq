import logging
from dimagi.utils.django.email import send_HTML_email
from django.contrib.auth.models import User
from corehq import Domain
from corehq.apps.users.models import WebUser, CommCareUser, CouchUser, DomainMembership
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
        'first_name': ilsgateway_webuser.first_name,
        'last_name': ilsgateway_webuser.last_name,
        'is_staff': ilsgateway_webuser.is_staff,
        'is_active': ilsgateway_webuser.is_active,
        'is_superuser': ilsgateway_webuser.is_superuser,
        'last_login': force_to_datetime(ilsgateway_webuser.last_login),
        'date_joined': force_to_datetime(ilsgateway_webuser.date_joined),
        #TODO Location and supply point
        #'location': ilsgateway_webuser.location,
        #'supply_point': ilsgateway_webuser.supply_point,
        'is_ilsuser': True,
    }

    role_id = ilsgateway_webuser.role_id if hasattr(ilsgateway_webuser, 'role_id') else None

    if user is None:
        try:
            user = WebUser.create(domain=None, username=ilsgateway_webuser.email.lower(),
                                  password=ilsgateway_webuser.password, email=ilsgateway_webuser.email, **user_dict)
            user.add_domain_membership(domain.name, role_id=role_id)
            user.save()
        except Exception as e:
            logging.error(e)
    else:
        if domain.name not in user.get_domains():
            user.add_domain_membership(domain.name, role_id=role_id)
            user.save()

    return user

def sync_ilsgateway_smsusers(domain, ilsgateway_smsuser):
    username_part = "%s%d" % (ilsgateway_smsuser.name.strip().replace(' ', '.').lower(), ilsgateway_smsuser.id)
    username = "%s@%s.commcarehq.org" % (username_part, domain.name)
    user = CouchUser.get_by_username(username)
    splitted_value = ilsgateway_smsuser.name.split(' ', 1)
    first_name = last_name = ''
    if splitted_value:
        first_name = splitted_value[0][:30] #due to postgres restriction
        last_name = splitted_value[1][:30] if len(splitted_value) > 1 else ''

    if user is None and username_part:
        try:
            password = User.objects.make_random_password()
            user = CommCareUser.create(domain=domain.name, username=username, password=password,
                                       email=ilsgateway_smsuser.email, commit=False)
            user.first_name = first_name
            user.last_name = last_name
            user.is_active = bool(ilsgateway_smsuser.is_active)
            if ilsgateway_smsuser.phone_numbers:
                user.set_default_phone_number(ilsgateway_smsuser.phone_numbers[0].replace('+', ''))
                user.user_data = {
                    'backend': ilsgateway_smsuser.backend
                }
                user.save()
        except Exception as e:
            logging.error(e)

    return user


def bootstrap_domain(domain):
    project = Domain.get_by_name(domain)
    if project.commtrack_settings and project.commtrack_settings.ilsgateway_config.is_configured:
        endpoint = ILSGatewayEndpoint.from_config(project.commtrack_settings.ilsgateway_config)
        for product in endpoint.get_products():
            sync_ilsgateway_product(domain, product)