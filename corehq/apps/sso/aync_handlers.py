from corehq.apps.accounting.async_handlers import BaseSelect2AsyncHandler
from corehq.apps.accounting.models import BillingAccount


class Select2IdentityProviderHandler(BaseSelect2AsyncHandler):
    slug = 'select2_identity_provider'
    allowed_actions = [
        'owner',
    ]

    @property
    def owner_response(self):
        accounts = BillingAccount.objects.filter(is_customer_billing_account=True)
        if self.search_string:
            accounts = accounts.filter(name__icontains=self.search_string)
        return [(a.id, a.name) for a in accounts.order_by('name')]


