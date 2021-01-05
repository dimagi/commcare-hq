from corehq.apps.sso import certificates
from dimagi.utils.data import generator as data_gen
from corehq.apps.accounting.tests import generator as accounting_gen

from corehq.util.test_utils import unit_testing_only
from corehq.apps.sso.models import (
    IdentityProvider,
)


@unit_testing_only
def create_idp(account=None, include_certs=False):
    if not account:
        account = get_billing_account_for_idp()
    idp_slug = data_gen.arbitrary_unique_name()[:20]
    idp = IdentityProvider(
        name=f"Azure AD for {account.name}",
        slug=idp_slug,
        owner=account
    )
    idp.save()
    if include_certs:
        idp.create_service_provider_certificate()
        idp.entity_id = "https://testidp.com/saml2/entity_id"
        idp.login_url = "https://testidp.com/saml2/login"
        idp.logout_url = "https://testidp.com/saml2/logout"
        key_pair = certificates.create_key_pair()
        cert = certificates.create_self_signed_cert(key_pair)
        idp.idp_cert_public = certificates.get_public_key(cert)
        idp.date_idp_cert_expiration = certificates.get_expiration_date(cert)
        idp.save()
    return idp


@unit_testing_only
def get_billing_account_for_idp():
    billing_contact = accounting_gen.create_arbitrary_web_user_name()
    dimagi_user = accounting_gen.create_arbitrary_web_user_name(is_dimagi=True)
    return accounting_gen.billing_account(
        dimagi_user, billing_contact, is_customer_account=True
    )
