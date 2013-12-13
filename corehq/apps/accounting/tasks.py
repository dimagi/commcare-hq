from celery.schedules import crontab
from celery.task import task, periodic_task
from celery.utils.log import get_task_logger
import datetime
from corehq import Domain
from corehq.apps.accounting import utils
from corehq.apps.accounting.invoicing import InvoiceFactory

from corehq.apps.accounting.models import Subscription

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
    # todo handle CommCare Community invoices... need to fetch all domains rather than subscriptions
    # and if no subscription found, use community
    invoice_start, invoice_end = utils.get_previous_month_date_range(today)
    invoiceable_subscriptions = Subscription.objects.filter(date_start__lt=invoice_end,
                                                            date_end__gt=invoice_start).all()
    for subscription in invoiceable_subscriptions:
        invoice_factory = InvoiceFactory(subscription, invoice_start, invoice_end)
        invoice_factory.create()

