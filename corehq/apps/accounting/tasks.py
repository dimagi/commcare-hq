from urllib import urlencode
from StringIO import StringIO
from celery.schedules import crontab
from celery.task import periodic_task, task
import datetime
from couchdbkit import ResourceNotFound
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, QueryDict
from django.template.loader import render_to_string
from django.utils.translation import ugettext

from corehq.apps.domain.models import Domain
from corehq.apps.accounting import utils
from corehq.apps.accounting.exceptions import (
    InvoiceError, CreditLineError,
    BillingContactInfoError,
    InvoiceAlreadyCreatedError
)
from corehq.apps.accounting.invoicing import DomainInvoiceFactory

from corehq.apps.accounting.models import (
    Subscription, Invoice,
    SubscriptionAdjustment, SubscriptionAdjustmentReason,
    SubscriptionAdjustmentMethod,
    BillingAccount, WirePrepaymentInvoice, WirePrepaymentBillingRecord
)
from corehq.apps.accounting.utils import (
    has_subscription_already_ended, get_dimagi_from_email_by_product,
    fmt_dollar_amount,
    get_change_status,
    log_accounting_error,
    log_accounting_info,
)
from corehq.apps.accounting.payment_handlers import AutoPayInvoicePaymentHandler
from corehq.apps.users.models import FakeUser, WebUser
from corehq.const import USER_DATE_FORMAT, USER_MONTH_FORMAT
from couchexport.export import export_from_tables
from couchexport.models import Format
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.django.email import send_HTML_email
import corehq.apps.accounting.filters as filters


def activate_subscriptions(based_on_date=None):
    """
    Activates all subscriptions starting today (or, for testing, based on the date specified)
    """
    starting_date = based_on_date or datetime.date.today()
    starting_subscriptions = Subscription.objects.filter(date_start=starting_date)
    for subscription in starting_subscriptions:
        if not has_subscription_already_ended(subscription) and not subscription.is_active:
            with transaction.atomic():
                subscription.is_active = True
                subscription.save()
                upgraded_privs = get_change_status(None, subscription.plan_version).upgraded_privs
                subscription.subscriber.activate_subscription(
                    upgraded_privileges=upgraded_privs,
                    subscription=subscription,
                )


def deactivate_subscriptions(based_on_date=None):
    """
    Deactivates all subscriptions ending today (or, for testing, based on the date specified)
    """
    ending_date = based_on_date or datetime.date.today()
    ending_subscriptions = Subscription.objects.filter(date_end=ending_date)
    for subscription in ending_subscriptions:
        with transaction.atomic():
            subscription.is_active = False
            subscription.save()
            next_subscription = subscription.next_subscription
            activate_next_subscription = next_subscription and next_subscription.date_start == ending_date
            if activate_next_subscription:
                new_plan_version = next_subscription.plan_version
                next_subscription.is_active = True
                next_subscription.save()
            else:
                new_plan_version = None
            _, downgraded_privs, upgraded_privs = get_change_status(subscription.plan_version, new_plan_version)
            if next_subscription and subscription.account == next_subscription.account:
                subscription.transfer_credits(subscription=next_subscription)
            else:
                subscription.transfer_credits()
            subscription.subscriber.deactivate_subscription(
                downgraded_privileges=downgraded_privs,
                upgraded_privileges=upgraded_privs,
                old_subscription=subscription,
                new_subscription=next_subscription if activate_next_subscription else None,
            )


@periodic_task(run_every=crontab(minute=0, hour=0))
def update_subscriptions():
    deactivate_subscriptions()
    activate_subscriptions()

@periodic_task(run_every=crontab(hour=13, minute=0, day_of_month='1'))
def generate_invoices(based_on_date=None, check_existing=False, is_test=False):
    """
    Generates all invoices for the past month.
    """
    today = based_on_date or datetime.date.today()
    invoice_start, invoice_end = utils.get_previous_month_date_range(today)
    log_accounting_info("Starting up invoices for %(start)s - %(end)s" % {
        'start': invoice_start.strftime(USER_DATE_FORMAT),
        'end': invoice_end.strftime(USER_DATE_FORMAT),
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
            log_accounting_info("Ready to create invoice for domain %s" % domain.name)
        else:
            try:
                invoice_factory = DomainInvoiceFactory(
                    invoice_start, invoice_end, domain)
                invoice_factory.create_invoices()
                log_accounting_info("Sent invoices for domain %s" % domain.name)
            except CreditLineError as e:
                log_accounting_error(
                    "There was an error utilizing credits for "
                    "domain %s: %s" % (domain.name, e)
                )
            except BillingContactInfoError as e:
                log_accounting_error("BillingContactInfoError: %s" % e)
            except InvoiceError as e:
                log_accounting_error(
                    "Could not create invoice for domain %s: %s" % (
                    domain.name, e
                ))
            except InvoiceAlreadyCreatedError as e:
                log_accounting_error(
                    "Invoice already existed for domain %s: %s" % (
                    domain.name, e
                ))
            except Exception as e:
                log_accounting_error(
                    "Error occurred while creating invoice for "
                    "domain %s: %s" % (domain.name, e)
                )


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
            "Invoices for %s" % datetime.date(year, month, 1).strftime(USER_MONTH_FORMAT),
            email,
            email_content,
            email_from=settings.DEFAULT_FROM_EMAIL,
            text_content=email_content_plaintext,
            file_attachments=[excel_attachment],
        )

    log_accounting_info(
        "Sent Bookkeeper Invoice Summary for %(month)s "
        "to %(emails)s." % {
            'month': first_of_month.strftime(USER_MONTH_FORMAT),
            'emails': ", ".join(emails)
        })


@periodic_task(run_every=crontab(minute=0, hour=0))
def remind_subscription_ending():
    """
    Sends reminder emails for subscriptions ending N days from now.
    """
    send_subscription_reminder_emails(30, exclude_trials=True)
    send_subscription_reminder_emails(10, exclude_trials=True)
    send_subscription_reminder_emails(1, exclude_trials=True)


@periodic_task(run_every=crontab(minute=0, hour=0))
def remind_dimagi_contact_subscription_ending_40_days():
    """
    Sends reminder emails to Dimagi contacts that subscriptions are ending in 40 days
    """
    send_subscription_reminder_emails_dimagi_contact(40)


def send_subscription_reminder_emails(num_days, exclude_trials=True):
    today = datetime.date.today()
    date_in_n_days = today + datetime.timedelta(days=num_days)
    ending_subscriptions = Subscription.objects.filter(date_end=date_in_n_days)
    if exclude_trials:
        ending_subscriptions = ending_subscriptions.filter(is_trial=False)
    for subscription in ending_subscriptions:
        try:
            # only send reminder emails if the subscription isn't renewed
            if not subscription.is_renewed:
                subscription.send_ending_reminder_email()
        except Exception as e:
            log_accounting_error(e.message)


def send_subscription_reminder_emails_dimagi_contact(num_days):
    today = datetime.date.today()
    date_in_n_days = today + datetime.timedelta(days=num_days)
    ending_subscriptions = (Subscription.objects
                            .filter(is_active=True)
                            .filter(date_end=date_in_n_days)
                            .filter(account__dimagi_contact__isnull=False))
    for subscription in ending_subscriptions:
        # only send reminder emails if the subscription isn't renewed
        if not subscription.is_renewed:
            subscription.send_dimagi_ending_reminder_email()


@task(ignore_result=True)
def create_wire_credits_invoice(domain_name,
                                account_created_by,
                                account_entry_point,
                                amount,
                                invoice_items,
                                contact_emails):
    account = BillingAccount.get_or_create_account_by_domain(
        domain_name,
        created_by=account_created_by,
        created_by_invoicing=True,
        entry_point=account_entry_point
    )[0]
    wire_invoice = WirePrepaymentInvoice.objects.create(
        domain=domain_name,
        date_start=datetime.datetime.utcnow(),
        date_end=datetime.datetime.utcnow(),
        date_due=None,
        balance=amount,
        account=account,
    )
    wire_invoice.items = invoice_items

    record = WirePrepaymentBillingRecord.generate_record(wire_invoice)
    try:
        record.send_email(contact_emails=contact_emails)
    except Exception as e:
        log_accounting_error(e.message)


@task(ignore_result=True)
def send_purchase_receipt(payment_record, core_product, domain,
                          template_html, template_plaintext,
                          additional_context):
    email = payment_record.payment_method.web_user

    try:
        web_user = WebUser.get_by_username(email)
        name = web_user.first_name
    except ResourceNotFound:
        log_accounting_error(
            "Strange. A payment attempt was made by a user that "
            "we can't seem to find! %s" % email
        )
        name = email

    context = {
        'name': name,
        'amount': fmt_dollar_amount(payment_record.amount),
        'project': domain,
        'date_paid': payment_record.date_created.strftime(USER_DATE_FORMAT),
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
            account__dimagi_contact__isnull=True,
        ))

    if not ending_in_forty_days:
        log_accounting_info(
            "Did not send summary of ending subscriptions because "
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
    env = ("[{}] ".format(settings.SERVER_ENVIRONMENT.upper())
           if settings.SERVER_ENVIRONMENT != "production" else "")
    email_subject = "{}Subscriptions ending in 40 Days from {}".format(env, today.isoformat())
    send_HTML_email(
        email_subject,
        settings.ACCOUNTS_EMAIL,
        email_content,
        email_from=from_email,
        text_content=email_content_plaintext,
        file_attachments=[file_attachment],
    )

    log_accounting_info(
        "Sent summary of ending subscriptions from %(today)s" % {
            'today': today.isoformat(),
        })


@periodic_task(run_every=crontab(hour=01, minute=0,))
def pay_autopay_invoices():
    """ Check for autopayable invoices every day and pay them """
    AutoPayInvoicePaymentHandler().pay_autopayable_invoices(datetime.datetime.today())
