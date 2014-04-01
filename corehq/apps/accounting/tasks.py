from urllib import urlencode
from celery.schedules import crontab
from celery.task import periodic_task
from celery.utils.log import get_task_logger
import datetime
from django.conf import settings
from django.http import HttpRequest, QueryDict
from django.template.loader import render_to_string
from corehq import Domain, toggles
from corehq.apps.accounting import utils
from corehq.apps.accounting.exceptions import InvoiceError, CreditLineError
from corehq.apps.accounting.invoicing import DomainInvoiceFactory

from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.utils import has_subscription_already_ended
from corehq.apps.users.models import FakeUser
from couchexport.models import Format
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.django.email import send_HTML_email

logger = get_task_logger('accounting')


@periodic_task(run_every=crontab(minute=0, hour=0))
def activate_subscriptions(based_on_date=None):
    """
    Activates all subscriptions starting today (or, for testing, based on the date specified)
    """
    starting_date = based_on_date or datetime.date.today()
    starting_subscriptions = Subscription.objects.filter(date_start=starting_date)
    for subscription in starting_subscriptions:
        if not has_subscription_already_ended(subscription):
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


@periodic_task(run_every=crontab(hour=13, minute=0, day_of_month='1'))
def generate_invoices(based_on_date=None):
    """
    Generates all invoices for the past month.
    """
    today = based_on_date or datetime.date.today()
    invoice_start, invoice_end = utils.get_previous_month_date_range(today)
    logger.info("[Billing] Starting up invoices for %(start)s - %(end)s" % {
        'start': invoice_start.strftime("%d %B %Y"),
        'end': invoice_end.strftime("%d %B %Y"),
    })
    all_domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
    for domain_doc in iter_docs(Domain.get_db(), all_domain_ids):
        domain = Domain.wrap(domain_doc)
        try:
            invoice_factory = DomainInvoiceFactory(
                invoice_start, invoice_end, domain)
            invoice_factory.create_invoices()
            logger.info("[BILLING] Sent invoices for domain %s"
                        % domain.name)
        except CreditLineError as e:
            logger.error(
                "[BILLING] There was an error utilizing credits for "
                "domain %s: %s" % (domain.name, e)
            )
        except InvoiceError as e:
            logger.error(
                "[BILLING] Could not create invoice for domain %s: %s" % (
                domain.name, e
            ))
    # And finally...
    send_bookkeeper_email()


def send_bookkeeper_email(month=None, year=None, emails=None):
    today = datetime.date.today()
    month = month or today.month
    year = year or today.year

    from corehq.apps.accounting.interface import InvoiceInterface
    request = HttpRequest()
    params = urlencode((
        ('report_filter_statement_period_month', month),
        ('report_filter_statement_period_year', year),
    ))
    request.GET = QueryDict(params)
    request.couch_user = FakeUser(
        domain="hqadmin",
        username="admin@dimagi.com",
    )
    invoice = InvoiceInterface(request)
    first_of_month = datetime.date(year, month, 1)
    email_context = {
        'month': first_of_month.strftime("%B"),
    }
    email_content = render_to_string(
        'accounting/bookkeeper_email.html', email_context)
    email_content_plaintext = render_to_string(
        'accounting/bookkeeper_email_plaintext.html', email_context)
    excel_attachment = {
        'title': 'Invoices_%s.xlsx' % first_of_month.strftime('%B_%Y'),
        'mimetype': Format.FORMAT_DICT[Format.XLS_2007]['mimetype'],
        'file_obj': invoice.excel_response,
    }

    emails = emails or settings.BOOKKEEPER_CONTACT_EMAILS
    for email in emails:
        send_HTML_email(
            "Invoices for %s" % datetime.date(year, month, 1).strftime("%B %Y"),
            email,
            email_content,
            email_from=settings.DEFAULT_FROM_EMAIL,
            text_content=email_content_plaintext,
            file_attachments=[excel_attachment],
        )

    logger.info(
        "[BILLING] Sent Bookkeeper Invoice Summary for %(month)s "
        "to %(emails)s." % {
            'month': first_of_month.strftime("%B %Y"),
            'emails': ", ".join(emails)
        })


