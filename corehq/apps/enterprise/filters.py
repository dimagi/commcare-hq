from django.utils.translation import ugettext_noop as _

from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.accounting.models import Subscription


class EnterpriseDomainFilter(BaseSingleOptionFilter):
    slug = "account"
    label = _("Project Space")

    @property
    def options(self):
        return [(domain, domain) for domain in Subscription.visible_objects.filter(
            account=self.request.account,
            is_active=True,
            account__is_active=True,
        ).values_list('subscriber__domain', flat=True).distinct()]
