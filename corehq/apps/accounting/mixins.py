from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.tasks import (
    get_unpaid_invoices_over_threshold_by_domain,
    is_subscription_eligible_for_downgrade_process,
)
from corehq.util.quickcache import quickcache


@quickcache(['domain_name'], timeout=60 * 60)
def get_overdue_invoice(domain_name):
    current_subscription = Subscription.get_active_subscription_by_domain(domain_name)
    if current_subscription and is_subscription_eligible_for_downgrade_process(current_subscription):
        overdue_invoice, _ = get_unpaid_invoices_over_threshold_by_domain(date.today(), domain_name)
        return overdue_invoice


class DowngradeModalMixin(object):

    @property
    def main_context(self):
        main_context = super(DowngradeModalMixin, self).main_context
        main_context.update(self._downgrade_modal_context)
        return main_context

    @property
    def _downgrade_modal_context(self):
        overdue_invoice = get_overdue_invoice(self.domain)
        context = {'show_overdue_invoice_modal': overdue_invoice is not None}
        if overdue_invoice:
            days_overdue = (date.today() - overdue_invoice.date_due).days
            context['invoice_month'] = overdue_invoice.date_start.strftime('%B %Y')
            context['days_until_downgrade'] = max(1, 61 - days_overdue)
        return context
