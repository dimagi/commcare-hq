import datetime

from django.db.models import Q, Sum

from corehq.apps.accounting.models import (
    Invoice,
    SubscriptionType,
    CustomerInvoice,
)

UNPAID_INVOICE_THRESHOLD = 100


def _get_all_unpaid_saas_invoices():
    return Invoice.objects.filter(
        is_hidden=False,
        subscription__service_type=SubscriptionType.PRODUCT,
        date_paid__isnull=True,
    )


def _get_unpaid_saas_invoices_in_downgrade_daterange(today):
    return _get_all_unpaid_saas_invoices().filter(
        date_due__lte=today - datetime.timedelta(days=1)
    ).order_by('date_due').select_related('subscription__subscriber')


def get_oldest_unpaid_invoice_over_threshold(today, domain):
    for overdue_invoice in _get_unpaid_saas_invoices_in_downgrade_daterange(today).filter(
        subscription__subscriber__domain=domain
    ):
        total_overdue_by_domain_and_invoice_date = _get_all_unpaid_saas_invoices().filter(
            Q(date_due__lte=overdue_invoice.date_due)
            | (Q(date_due__isnull=True) & Q(date_end__lte=overdue_invoice.date_end)),
            subscription__subscriber__domain=domain,
        ).aggregate(Sum('balance'))['balance__sum']
        if total_overdue_by_domain_and_invoice_date >= UNPAID_INVOICE_THRESHOLD:
            return overdue_invoice, total_overdue_by_domain_and_invoice_date
    return None, None


def get_domains_with_subscription_invoices_over_threshold(today):
    for domain in set(_get_unpaid_saas_invoices_in_downgrade_daterange(today).values_list(
        'subscription__subscriber__domain', flat=True
    )):
        overdue_invoice, total_overdue_to_date = get_oldest_unpaid_invoice_over_threshold(today, domain)
        if overdue_invoice:
            yield domain, overdue_invoice, total_overdue_to_date


def get_accounts_with_customer_invoices_over_threshold(today):
    unpaid_customer_invoices = CustomerInvoice.objects.filter(
        is_hidden=False,
        date_paid__isnull=True
    )

    overdue_customer_invoices_in_downgrade_daterange = unpaid_customer_invoices.filter(
        date_due__lte=today - datetime.timedelta(days=1),
        date_due__gte=today - datetime.timedelta(days=61)
    ).order_by('date_due').select_related('account')

    accounts = set()
    for overdue_invoice in overdue_customer_invoices_in_downgrade_daterange:
        account = overdue_invoice.account.name
        plan = overdue_invoice.subscriptions.first().plan_version
        if (account, plan) not in accounts:
            invoices = unpaid_customer_invoices.filter(
                Q(date_due__lte=overdue_invoice.date_due)
                | (Q(date_due__isnull=True) & Q(date_end__lte=overdue_invoice.date_end)),
                account__name=account
            )
            invoices = [invoice for invoice in invoices if invoice.subscriptions.first().plan_version == plan]
            total_overdue_to_date = sum(invoice.balance for invoice in invoices)

            if total_overdue_to_date >= UNPAID_INVOICE_THRESHOLD:
                accounts.add((account, plan))
                yield overdue_invoice, total_overdue_to_date
