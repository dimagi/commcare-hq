from corehq.apps.accounting.filters import clean_options
from django.utils.translation import ugettext_lazy

from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.accounting.models import BillingAccount, Subscription


class EnterpriseDomainFilter(BaseSingleOptionFilter):
    slug = "account"
    label = ugettext_lazy("Project Space")

    @property
    def options(self):
        account = BillingAccount.get_account_by_domain(self.request.domain)
        return clean_options([(domain, domain) for domain in Subscription.get_active_domains_for_account(account)])
