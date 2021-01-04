from dimagi.utils.data import generator as data_gen
from corehq.apps.accounting.tests import generator as accounting_gen

from corehq.util.test_utils import unit_testing_only
from corehq.apps.sso.models import (
    IdentityProvider,
)


@unit_testing_only
def create_idp(account=None):
    if not account:
        account = get_billing_account_for_idp()
    idp_slug = data_gen.arbitrary_unique_name()[:20]
    idp = IdentityProvider(
        name=f"Azure AD for {account.name}",
        slug=idp_slug,
        owner=account
    )
    idp.save()
    return idp


@unit_testing_only
def get_billing_account_for_idp():
    billing_contact = accounting_gen.create_arbitrary_web_user_name()
    dimagi_user = accounting_gen.create_arbitrary_web_user_name(is_dimagi=True)
    return accounting_gen.billing_account(
        dimagi_user, billing_contact, is_customer_account=True
    )
