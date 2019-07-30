from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import itertools
from datetime import date, timedelta

from corehq.apps.accounting.models import CreditLine, Subscription
from corehq.apps.accounting.tasks import (
    get_unpaid_invoices_over_threshold_by_domain,
    is_subscription_eligible_for_downgrade_process,
)
from corehq.apps.accounting.utils import months_from_date
from corehq.apps.users.decorators import get_permission_name
from corehq.apps.users.models import Permissions
from corehq.util.quickcache import quickcache


@quickcache(['domain_name'], timeout=60 * 60)
def get_overdue_invoice(domain_name):
    current_subscription = Subscription.get_active_subscription_by_domain(domain_name)
    if current_subscription and is_subscription_eligible_for_downgrade_process(current_subscription):
        overdue_invoice, _ = get_unpaid_invoices_over_threshold_by_domain(date.today(), domain_name)
        return overdue_invoice


def get_total_credits_available_for_product(subscription):
    return (
        get_credits_available_for_product_in_subscription(subscription)
        + get_credits_available_for_product_in_account(subscription.account)
    )


@quickcache(['current_subscription.id'], timeout=60 * 60)
def get_credits_available_for_product_in_subscription(current_subscription):
    return sum([
        credit_line.balance for credit_line in itertools.chain(
            CreditLine.get_credits_by_subscription_and_features(current_subscription, is_product=True),
            CreditLine.get_credits_by_subscription_and_features(current_subscription),
        )
    ])


@quickcache(['account.id'], timeout=60 * 60)
def get_credits_available_for_product_in_account(account):
    return sum([
        credit_line.balance for credit_line in itertools.chain(
            CreditLine.get_credits_for_account(account, is_product=True),
            CreditLine.get_credits_for_account(account),
        )
    ])


class BillingModalsMixin(object):

    @property
    def main_context(self):
        main_context = super(BillingModalsMixin, self).main_context
        if self._should_display_billing_modals():
            main_context.update(self._downgrade_modal_context)
            main_context.update(self._low_credits_context)
        return main_context

    def _should_display_billing_modals(self):
        return (
            self.request.couch_user
            and not self.request.couch_user.is_superuser
            and self.request.couch_user.has_permission(
                self.domain,
                get_permission_name(Permissions.edit_billing)
            )
        )

    @property
    def _downgrade_modal_context(self):
        overdue_invoice = get_overdue_invoice(self.domain)
        context = {'show_overdue_invoice_modal': overdue_invoice is not None}
        if overdue_invoice:
            days_overdue = (date.today() - overdue_invoice.date_due).days
            context['invoice_month'] = overdue_invoice.date_start.strftime('%B %Y')
            context['days_until_downgrade'] = max(1, 61 - days_overdue)
        return context

    @property
    def _low_credits_context(self):
        context = {}
        current_subscription = Subscription.get_active_subscription_by_domain(self.domain)
        if current_subscription:
            monthly_fee = current_subscription.plan_version.product_rate.monthly_fee
            if monthly_fee:
                prepaid_credits = get_total_credits_available_for_product(current_subscription)
                num_months_remaining = prepaid_credits / monthly_fee
                prepaid_remaining_date = months_from_date(date.today(), num_months_remaining)
                partial_month_remaining = num_months_remaining % 1
                num_days_in_month = 30  # Approximate
                prepaid_remaining_date += timedelta(days=int(partial_month_remaining * num_days_in_month))
                prepaid_days_remaining = (prepaid_remaining_date - date.today()).days
                if 0 < prepaid_days_remaining < 63:
                    context['show_prepaid_modal'] = True
                    context['prepaid_days_remaining'] = prepaid_days_remaining
                    context['prepaid_weeks_remaining'] = max(prepaid_days_remaining // 7, 1)
                    context['monthly_fee'] = monthly_fee
                    context['edition'] = current_subscription.plan_version.plan.edition
                    context['prepaid_remaining_date'] = prepaid_remaining_date
        return context
