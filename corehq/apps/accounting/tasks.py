from celery.schedules import crontab
from celery.task import task, periodic_task
from celery.utils.log import get_task_logger
import datetime
from django.core.exceptions import ObjectDoesNotExist
from corehq import Domain
from corehq.apps.accounting import utils
from corehq.apps.accounting.invoicing import SubscriptionInvoiceFactory, CommunityInvoiceFactory

from corehq.apps.accounting.models import Subscription
from corehq.apps.orgs.models import Organization
from dimagi.utils.couch.database import iter_docs

logging = get_task_logger(__name__)


@periodic_task(run_every=crontab(minute=0, hour=0))
def activate_subscriptions(based_on_date=None):
    """
    Activates all subscriptions starting today (or, for testing, based on the date specified)
    """
    starting_date = based_on_date or datetime.date.today()
    starting_subscriptions = Subscription.objects.filter(date_start=starting_date)
    for subscription in starting_subscriptions:
        subscription.is_active = True
        subscription.save()


@periodic_task(run_every=crontab(minute=0, hour=0))
def deactivate_subscriptions(based_on_date=None):
    """
    Deactivates all subscriptions ending yesterday (or, for testing, based on the date specified)
    """
    ending_date = based_on_date or datetime.date.today()
    ending_subscriptions = Subscription.objects.filter(date_end=ending_date)
    for subscription in ending_subscriptions:
        subscription.is_active = False
        subscription.save()


@task
def generate_invoices(based_on_date=None):
    """
    Generates all invoices for the past month.
    """
    today = based_on_date or datetime.date.today()
    invoice_start, invoice_end = utils.get_previous_month_date_range(today)
    invoiceable_subscriptions = Subscription.objects.filter(date_start__lt=invoice_end,
                                                            date_end__gt=invoice_start).all()

    def _create_invoice(sub):
        invoice_factory = SubscriptionInvoiceFactory(invoice_start, invoice_end, sub)
        invoice_factory.create()

    invoiced_orgs = []
    orgs = Organization.get_db().view('orgs/by_name', group=True, group_level=1).all()
    org_names = [o['key'] for o in orgs]
    for org_name in org_names:
        try:
            subscription = invoiceable_subscriptions.get(subscriber__organization=org_name)
        except ObjectDoesNotExist:
            continue
        _create_invoice(subscription)
        invoiced_orgs.append(org_name)

    all_domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
    for domain_doc in iter_docs(Domain.get_db(), all_domain_ids):
        domain_name = domain_doc['name']
        domain_org = domain_doc['organization']
        try:
            subscription = invoiceable_subscriptions.get(subscriber__domain=domain_name)
        except ObjectDoesNotExist:
            if domain_org not in invoiced_orgs:
                domain = Domain.wrap(domain_doc)
                invoice_factory = CommunityInvoiceFactory(invoice_start, invoice_end, domain)
                invoice_factory.create()
            continue
        _create_invoice(subscription)

