from urllib import urlencode
from StringIO import StringIO
from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger
import datetime
from couchdbkit import ResourceNotFound
from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpRequest, QueryDict
from django.template.loader import render_to_string
from django.utils.translation import ugettext
from corehq import toggles
from django.db import models
from corehq.apps.domain.models import Domain
from corehq.apps.accounting import utils
from corehq.apps.accounting.exceptions import InvoiceError, CreditLineError, BillingContactInfoError
from corehq.apps.accounting.invoicing import DomainInvoiceFactory

from corehq.apps.accounting.models import (
    Subscription, Invoice, BillingAccount, BillingAccountType,
    SubscriptionAdjustment, SubscriptionAdjustmentReason,
    SubscriptionAdjustmentMethod)
from corehq.apps.accounting.utils import (
    has_subscription_already_ended, get_dimagi_from_email_by_product,
    fmt_dollar_amount,
)
from corehq.apps.users.models import FakeUser, WebUser
from couchexport.export import export_from_tables
from couchexport.models import Format
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.django.email import send_HTML_email
import corehq.apps.accounting.filters as filters

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
    Deactivates all subscriptions ending today (or, for testing, based on the date specified)
    """
    ending_date = based_on_date or datetime.date.today()
    ending_subscriptions = Subscription.objects.filter(date_end=ending_date)
    for subscription in ending_subscriptions:
        subscription.is_active = False
        subscription.save()


@periodic_task(run_every=crontab(hour=13, minute=0, day_of_month='1'))
def generate_invoices(based_on_date=None, check_existing=False, is_test=False):
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
        if (check_existing and
            Invoice.objects.filter(
                subscription__subscriber__domain=domain,
                date_created__gte=today).count() != 0):
            pass
        elif is_test:
            logger.info("[Billing] Ready to create invoice for domain %s"
                        % domain.name)
        else:
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
            except BillingContactInfoError as e:
                logger.info("BillingContactInfoError: %s" % e)
            except InvoiceError as e:
                logger.error(
                    "[BILLING] Could not create invoice for domain %s: %s" % (
                    domain.name, e
                ))
            except Exception as e:
                logger.error(
                    "[BILLING] Error occurred while creating invoice for "
                    "domain %s: %s" % (domain.name, e)
                )
    # And finally...
    if not is_test:
        send_bookkeeper_email()


def send_bookkeeper_email(month=None, year=None, emails=None):
    today = datetime.date.today()

    # now, make sure that we send out LAST month's invoices if we did
    # not specify a month or year.
    today = utils.get_previous_month_date_range(today)[0]

    month = month or today.month
    year = year or today.year

    from corehq.apps.accounting.interface import InvoiceInterface
    request = HttpRequest()
    params = urlencode((
        ('report_filter_statement_period_use_filter', 'on'),
        ('report_filter_statement_period_month', month),
        ('report_filter_statement_period_year', year),
    ))
    request.GET = QueryDict(params)
    request.couch_user = FakeUser(
        domain="hqadmin",
        username="admin@dimagi.com",
    )
    invoice = InvoiceInterface(request)
    invoice.is_rendered_as_email = True
    first_of_month = datetime.date(year, month, 1)
    email_context = {
        'month': first_of_month.strftime("%B"),
    }
    email_content = render_to_string(
        'accounting/bookkeeper_email.html', email_context)
    email_content_plaintext = render_to_string(
        'accounting/bookkeeper_email_plaintext.html', email_context)

    format_dict = Format.FORMAT_DICT[Format.CSV]
    excel_attachment = {
        'title': 'Invoices_%(period)s.%(extension)s' % {
            'period': first_of_month.strftime('%B_%Y'),
            'extension': format_dict['extension'],
        },
        'mimetype': format_dict['mimetype'],
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


@periodic_task(run_every=crontab(minute=0, hour=0))
def remind_subscription_ending_30_days():
    """
    Sends reminder emails for subscriptions ending 30 days from now.
    """
    send_subscription_reminder_emails(30)


@periodic_task(run_every=crontab(minute=0, hour=0))
def remind_subscription_ending_30_days(based_on_date=None):
    """
    Sends reminder emails for subscriptions ending 10 days from now.
    """
    send_subscription_reminder_emails(10, exclude_trials=False)


@periodic_task(run_every=crontab(minute=0, hour=0))
def remind_subscription_ending_30_days(based_on_date=None):
    """
    Sends reminder emails for subscriptions ending tomorrow.
    """
    send_subscription_reminder_emails(1, exclude_trials=False)


def send_subscription_reminder_emails(num_days, exclude_trials=True):
    today = datetime.date.today()
    date_in_n_days = today + datetime.timedelta(days=num_days)
    ending_subscriptions = Subscription.objects.filter(date_end=date_in_n_days)
    if exclude_trials:
        ending_subscriptions.filter(is_trial=False)
    for subscription in ending_subscriptions:
        # only send reminder emails if the subscription isn't renewed
        if not subscription.is_renewed:
            subscription.send_ending_reminder_email()


@task
def send_purchase_receipt(payment_record, core_product,
                          template_html, template_plaintext,
                          additional_context):
    email = payment_record.payment_method.billing_admin.web_user

    try:
        web_user = WebUser.get_by_username(email)
        name = web_user.first_name
    except ResourceNotFound:
        logger.error(
            "[BILLING] Strange. A payment attempt was made by a user that "
            "we can't seem to find! %s" % email
        )
        name = email

    context = {
        'name': name,
        'amount': fmt_dollar_amount(payment_record.amount),
        'project': payment_record.payment_method.billing_admin.domain,
        'date_paid': payment_record.date_created.strftime('%d %B %Y'),
        'product': core_product,
        'transaction_id': payment_record.public_transaction_id,
    }
    context.update(additional_context)

    email_html = render_to_string(template_html, context)
    email_plaintext = render_to_string(template_plaintext, context)

    send_HTML_email(
        ugettext("Payment Received - Thank You!"), email, email_html,
        text_content=email_plaintext,
        email_from=get_dimagi_from_email_by_product(core_product),
    )


# Email this out every Monday morning.
@periodic_task(run_every=crontab(minute=0, hour=0, day_of_week=1))
def weekly_digest():
    today = datetime.date.today()
    in_forty_days = today + datetime.timedelta(days=40)

    ending_in_forty_days = filter(
        lambda sub: not sub.is_renewed,
        Subscription.objects.filter(
            date_end__lte=in_forty_days,
            date_end__gte=today,
            is_active=True,
            is_trial=False,
        ))

    if not ending_in_forty_days:
        logger.info(
            "[Billing] Did not send summary of ending subscriptions because "
            "there are none."
        )
        return

    table = [[
        "Project Space", "Account", "Plan", "Salesforce Contract ID",
        "Dimagi Contact", "Start Date", "End Date", "Receives Invoice",
        "Created By",
    ]]

    def _fmt_row(sub):
        try:
            created_by_adj = SubscriptionAdjustment.objects.filter(
                subscription=sub,
                reason=SubscriptionAdjustmentReason.CREATE
            ).order_by('date_created')[0]
            created_by = dict(SubscriptionAdjustmentMethod.CHOICES).get(
                created_by_adj.method, "Unknown")
        except (IndexError, SubscriptionAdjustment.DoesNotExist):
            created_by = "Unknown"
        return [
            sub.subscriber.domain,
            "%s (%s)" % (sub.account.name, sub.account.id),
            sub.plan_version.plan.name,
            sub.salesforce_contract_id,
            sub.account.dimagi_contact,
            sub.date_start,
            sub.date_end,
            "No" if sub.do_not_invoice else "YES",
            created_by,
        ]

    table.extend([_fmt_row(sub) for sub in ending_in_forty_days])

    file_to_attach = StringIO()
    export_from_tables(
        [['End in 40 Days', table]],
        file_to_attach,
        Format.XLS_2007
    )

    email_context = {
        'today': today.isoformat(),
        'forty_days': in_forty_days.isoformat(),
    }
    email_content = render_to_string(
        'accounting/digest_email.html', email_context)
    email_content_plaintext = render_to_string(
        'accounting/digest_email.txt', email_context)

    format_dict = Format.FORMAT_DICT[Format.XLS_2007]
    file_attachment = {
        'title': 'Subscriptions_%(start)s_%(end)s.xls' % {
            'start': today.isoformat(),
            'end': in_forty_days.isoformat(),
        },
        'mimetype': format_dict['mimetype'],
        'file_obj': file_to_attach,
    }
    from_email = "Dimagi Accounting <%s>" % settings.DEFAULT_FROM_EMAIL
    send_HTML_email(
        "Subscriptions ending in 40 Days from %s" % today.isoformat(),
        settings.INVOICING_CONTACT_EMAIL,
        email_content,
        email_from=from_email,
        text_content=email_content_plaintext,
        file_attachments=[file_attachment],
    )

    logger.info(
        "[BILLING] Sent summary of ending subscriptions from %(today)s" % {
            'today': today.isoformat(),
        })
