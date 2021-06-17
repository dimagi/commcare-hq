from corehq.apps.accounting.filters import clean_options
from django.utils.translation import ugettext_lazy

from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.accounting.models import Subscription


class EnterpriseDomainFilter(BaseSingleOptionFilter):
    slug = "account"
    label = ugettext_lazy("Project Space")

    @property
    def options(self):
        return clean_options([(domain, domain) for domain in Subscription.visible_objects.filter(
            account=self.request.account,
            is_active=True,
            account__is_active=True,
        ).values_list('subscriber__domain', flat=True).distinct()])
