import datetime

from django.db.models import Q, Sum

from corehq.apps.accounting.models import Invoice
from corehq.apps.accounting.models import SubscriptionType

UNPAID_INVOICE_THRESHOLD = 100


def get_all_unpaid_saas_invoices():
    return Invoice.objects.filter(
        is_hidden=False,
        subscription__service_type=SubscriptionType.PRODUCT,
        date_paid__isnull=True,
    )


def get_unpaid_saas_invoices_in_downgrade_daterange(today):
    return get_all_unpaid_saas_invoices().filter(
        date_due__lte=today - datetime.timedelta(days=1)
    ).order_by('date_due').select_related('subscription__subscriber')


def get_unpaid_invoices_over_threshold_by_domain(today, domain):
    for overdue_invoice in get_unpaid_saas_invoices_in_downgrade_daterange(today).filter(
        subscription__subscriber__domain=domain
    ):
        total_overdue_by_domain_and_invoice_date = get_all_unpaid_saas_invoices().filter(
            Q(date_due__lte=overdue_invoice.date_due)
            | (Q(date_due__isnull=True) & Q(date_end__lte=overdue_invoice.date_end)),
            subscription__subscriber__domain=domain,
        ).aggregate(Sum('balance'))['balance__sum']
        if total_overdue_by_domain_and_invoice_date >= UNPAID_INVOICE_THRESHOLD:
            return overdue_invoice, total_overdue_by_domain_and_invoice_date
    return None, None


def get_domains_with_subscription_invoices_over_threshold(today):
    for domain in set(get_unpaid_saas_invoices_in_downgrade_daterange(today).values_list(
        'subscription__subscriber__domain', flat=True
    )):
        overdue_invoice, total_overdue_to_date = get_unpaid_invoices_over_threshold_by_domain(today, domain)
        if overdue_invoice:
            yield domain, overdue_invoice, total_overdue_to_date
