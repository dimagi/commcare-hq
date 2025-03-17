import datetime

from django.db.models import Q, Sum

from corehq.apps.accounting.const import (
    DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER,
    DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE,
)
from corehq.apps.accounting.models import (
    CustomerInvoice,
    Invoice,
    SubscriptionType,
)

UNPAID_INVOICE_THRESHOLD = 1


def _get_all_unpaid_saas_invoices():
    return Invoice.objects.filter(
        is_hidden=False,
        subscription__service_type=SubscriptionType.PRODUCT,
        date_paid__isnull=True,
    )


def get_domains_with_subscription_invoices_overdue(today):
    invoices = _get_unpaid_saas_invoices_in_downgrade_daterange(today)
    return _get_domains_over_threshold(invoices, today, get_oldest_overdue_invoice_over_threshold)


def get_domains_with_subscription_invoices_due_soon(today):
    invoices = _get_unpaid_saas_invoices_in_reminder_daterange(today)
    return _get_domains_over_threshold(invoices, today, get_oldest_due_soon_invoice_over_threshold)


def _get_unpaid_saas_invoices_in_downgrade_daterange(today):
    return _get_all_unpaid_saas_invoices().filter(
        date_due__lte=today - datetime.timedelta(days=1)
    ).order_by('date_due').select_related('subscription__subscriber')


def _get_unpaid_saas_invoices_in_reminder_daterange(today):
    date_start = today + datetime.timedelta(days=1)
    date_end = today + datetime.timedelta(days=DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER)
    return _get_all_unpaid_saas_invoices().filter(
        date_due__gte=date_start,
        date_due__lte=date_end,
    ).order_by('date_due').select_related('subscription__subscriber')


def _get_domains_over_threshold(invoices, today, get_oldest_invoice_fn):
    for domain in set(invoices.values_list(
        'subscription__subscriber__domain', flat=True
    )):
        unpaid_invoice, total_unpaid = get_oldest_invoice_fn(today, domain)
        if unpaid_invoice:
            yield domain, unpaid_invoice, total_unpaid


def get_oldest_overdue_invoice_over_threshold(today, domain):
    invoices = _get_unpaid_saas_invoices_in_downgrade_daterange(today)
    return _get_oldest_invoice_over_threshold(domain, invoices)


def get_oldest_due_soon_invoice_over_threshold(today, domain):
    invoices = _get_unpaid_saas_invoices_in_reminder_daterange(today)
    return _get_oldest_invoice_over_threshold(domain, invoices)


def _get_oldest_invoice_over_threshold(domain, invoices):
    for unpaid_invoice in invoices.filter(
        subscription__subscriber__domain=domain
    ):
        total_unpaid_by_domain_and_invoice_date = _get_all_unpaid_saas_invoices().filter(
            Q(date_due__lte=unpaid_invoice.date_due)
            | (Q(date_due__isnull=True) & Q(date_end__lte=unpaid_invoice.date_end)),
            subscription__subscriber__domain=domain,
        ).aggregate(Sum('balance'))['balance__sum']
        if total_unpaid_by_domain_and_invoice_date >= UNPAID_INVOICE_THRESHOLD:
            return unpaid_invoice, total_unpaid_by_domain_and_invoice_date
    return None, None


def get_accounts_with_customer_invoices_due_soon(today):
    date_start = today + datetime.timedelta(days=1)
    date_end = today + datetime.timedelta(days=DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER)
    return _get_accounts_over_threshold_in_daterange(date_start, date_end)


def get_accounts_with_customer_invoices_overdue(today):
    date_start = today - datetime.timedelta(days=DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE)
    date_end = today - datetime.timedelta(days=1)
    return _get_accounts_over_threshold_in_daterange(date_start, date_end)


def _get_accounts_over_threshold_in_daterange(date_start, date_end):
    unpaid_customer_invoices = CustomerInvoice.objects.filter(
        is_hidden=False,
        date_paid__isnull=True,
    )
    unpaid_customer_invoices_in_daterange = unpaid_customer_invoices.objects.filter(
        date_due__gte=date_start,
        date_due__lte=date_end,
    ).order_by('date_due').select_related('account')

    accounts = set()
    for unpaid_invoice in unpaid_customer_invoices_in_daterange:
        account = unpaid_invoice.account.name
        plan = unpaid_invoice.subscriptions.first().plan_version
        if (account, plan) not in accounts:
            invoices = unpaid_customer_invoices.filter(
                Q(date_due__lte=unpaid_invoice.date_due)
                | (Q(date_due__isnull=True) & Q(date_end__lte=unpaid_invoice.date_end)),
                account__name=account
            )
            invoices = [invoice for invoice in invoices if invoice.subscriptions.first().plan_version == plan]
            total_unpaid_to_date = sum(invoice.balance for invoice in invoices)

            if total_unpaid_to_date >= UNPAID_INVOICE_THRESHOLD:
                accounts.add((account, plan))
                yield unpaid_invoice, total_unpaid_to_date
