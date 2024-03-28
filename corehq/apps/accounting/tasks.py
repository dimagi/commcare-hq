import csv
import datetime
import io
import json
from datetime import date

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpRequest, QueryDict
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request
from celery.schedules import crontab
from couchdbkit import ResourceConflict
from dateutil.relativedelta import relativedelta
from six.moves.urllib.parse import urlencode

from couchexport.export import export_from_tables
from couchexport.models import Format
from dimagi.utils.couch.database import iter_docs

from corehq.apps.accounting.automated_reports import CreditsAutomatedReport
from corehq.apps.accounting.exceptions import (
    ActiveSubscriptionWithoutDomain,
    CreditLineBalanceMismatchError,
    CreditLineError,
    InvoiceError,
    MultipleActiveSubscriptionsError,
    NoActiveSubscriptionError,
    SubscriptionTaskError,
)
from corehq.apps.accounting.invoicing import (
    CustomerAccountInvoiceFactory,
    DomainInvoiceFactory,
)
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingAccountWebUserHistory,
    CreditLine,
    Currency,
    DomainUserHistory,
    FeatureType,
    InvoicingPlan,
    Subscription,
    SubscriptionAdjustment,
    SubscriptionAdjustmentMethod,
    SubscriptionAdjustmentReason,
    SubscriptionType,
    WirePrepaymentBillingRecord,
    WirePrepaymentInvoice,
)
from corehq.apps.accounting.payment_handlers import (
    AutoPayInvoicePaymentHandler,
)
from corehq.apps.accounting.task_utils import (
    get_context_to_send_autopay_failed_email,
    get_context_to_send_purchase_receipt,
)
from corehq.apps.accounting.utils import (
    get_change_status,
    log_accounting_error,
    log_accounting_info,
)
from corehq.apps.accounting.utils.downgrade import downgrade_eligible_domains
from corehq.apps.accounting.utils.subscription import (
    assign_explicit_unpaid_subscription,
)
from corehq.apps.app_manager.dbaccessors import get_all_apps
from corehq.apps.celery import periodic_task, task
from corehq.apps.domain.models import Domain
from corehq.apps.hqmedia.models import ApplicationMediaMixin
from corehq.apps.users.models import CommCareUser, FakeUser
from corehq.const import (
    SERVER_DATE_FORMAT,
    SERVER_DATETIME_FORMAT_NO_SEC,
    USER_DATE_FORMAT,
    USER_MONTH_FORMAT,
)
from corehq.util.dates import get_previous_month_date_range
from corehq.util.log import send_HTML_email
from corehq.util.serialization import deserialize_decimal
from corehq.util.soft_assert import soft_assert

_invoicing_complete_soft_assert = soft_assert(
    to=[
        '{}@{}'.format(name, 'dimagi.com')
        for name in ['gbova', 'dmore', 'accounts']
    ],
    exponential_backoff=False,
)


@transaction.atomic
def _activate_subscription(subscription):
    subscription.is_active = True
    subscription.save()
    upgraded_privs = get_change_status(None, subscription.plan_version).upgraded_privs
    subscription.subscriber.activate_subscription(
        upgraded_privileges=upgraded_privs,
        subscription=subscription,
    )


def activate_subscriptions(based_on_date=None):
    starting_subscriptions = Subscription.visible_objects.filter(
        Q(date_end__isnull=True) | Q(date_end__gt=F('date_start')),
        is_active=False,
    )
    if based_on_date:
        starting_subscriptions = starting_subscriptions.filter(date_start=based_on_date)
    else:
        today = date.today()
        starting_subscriptions = starting_subscriptions.filter(
            date_start__lte=today,
            date_end__gt=today,
        )

    for subscription in starting_subscriptions:
        try:
            _activate_subscription(subscription)
        except Exception as e:
            log_accounting_error(
                'Error activating subscription %d: %s' % (subscription.id, str(e)),
                show_stack_trace=True,
            )


@transaction.atomic
def _deactivate_subscription(subscription):
    subscription.is_active = False
    subscription.save()
    next_subscription = subscription.next_subscription
    activate_next_subscription = next_subscription and next_subscription.date_start == subscription.date_end
    if activate_next_subscription:
        new_plan_version = next_subscription.plan_version
        next_subscription.is_active = True
        next_subscription.save()
    else:
        domain = subscription.subscriber.domain
        if not subscription.account.is_customer_billing_account:
            account = subscription.account
        else:
            account = BillingAccount.create_account_for_domain(
                domain, created_by='deactivation_after_customer_level'
            )
        next_subscription = assign_explicit_unpaid_subscription(
            domain,
            subscription.date_end,
            SubscriptionAdjustmentMethod.AUTOMATIC_DOWNGRADE,
            account=account,
            is_paused=True
        )
        new_plan_version = next_subscription.plan_version
    _, downgraded_privs, upgraded_privs = get_change_status(subscription.plan_version, new_plan_version)
    if subscription.account == next_subscription.account:
        subscription.transfer_credits(subscription=next_subscription)
    else:
        subscription.transfer_credits()
    subscription.subscriber.deactivate_subscription(
        downgraded_privileges=downgraded_privs,
        upgraded_privileges=upgraded_privs,
        old_subscription=subscription,
        new_subscription=next_subscription if activate_next_subscription else None,
    )


def deactivate_subscriptions(based_on_date=None):
    ending_subscriptions = Subscription.visible_objects.filter(
        is_active=True,
    )
    if based_on_date:
        ending_subscriptions = ending_subscriptions.filter(date_end=based_on_date)
    else:
        ending_subscriptions = ending_subscriptions.filter(date_end__lte=datetime.date.today())

    for subscription in ending_subscriptions:
        try:
            _deactivate_subscription(subscription)
        except Exception as e:
            log_accounting_error(
                'Error deactivating subscription %d: %s' % (subscription.id, str(e)),
                show_stack_trace=True,
            )


def warn_subscriptions_still_active(based_on_date=None):
    ending_date = based_on_date or datetime.date.today()
    subscriptions_still_active = Subscription.visible_objects.filter(
        date_end__lte=ending_date,
        is_active=True,
    )
    for subscription in subscriptions_still_active:
        try:
            # needed for sending to sentry
            raise SubscriptionTaskError()
        except SubscriptionTaskError:
            log_accounting_error(f"{subscription} is still active.")


def warn_subscriptions_not_active(based_on_date=None):
    based_on_date = based_on_date or datetime.date.today()
    subscriptions_not_active = Subscription.visible_objects.filter(
        Q(date_end=None) | Q(date_end__gt=based_on_date),
        date_start__lte=based_on_date,
        is_active=False,
    )
    for subscription in subscriptions_not_active:
        try:
            # needed for sending to sentry
            raise SubscriptionTaskError()
        except SubscriptionTaskError:
            log_accounting_error(f"{subscription} is not active.")


def warn_active_subscriptions_per_domain_not_one():
    for domain_name in Domain.get_all_names():
        active_subscription_count = Subscription.visible_objects.filter(
            subscriber__domain=domain_name,
            is_active=True,
        ).count()

        # we need to put a try/except here so that sentry captures logging
        try:
            if active_subscription_count > 1:
                raise MultipleActiveSubscriptionsError()
            elif active_subscription_count == 0 and Domain.get_by_name(domain_name).is_active:
                raise NoActiveSubscriptionError()
        except NoActiveSubscriptionError:
            log_accounting_error(
                f"There is no active subscription for domain {domain_name}"
            )
        except MultipleActiveSubscriptionsError:
            log_accounting_error(
                f"Multiple active subscriptions found for domain {domain_name}"
            )


def warn_subscriptions_without_domain():
    domains_with_active_subscription = Subscription.visible_objects.filter(
        is_active=True,
    ).values_list('subscriber__domain', flat=True).distinct()
    for domain_name in set(domains_with_active_subscription) - set(Domain.get_all_names()):
        # we need to put a try/except here so that sentry captures logging
        try:
            raise ActiveSubscriptionWithoutDomain()
        except ActiveSubscriptionWithoutDomain:
            log_accounting_error(
                f'Domain {domain_name} has an active subscription but does not exist.'
            )


@periodic_task(run_every=crontab(minute=0, hour=5), acks_late=True)
def update_subscriptions():
    deactivate_subscriptions(datetime.date.today())
    deactivate_subscriptions()
    activate_subscriptions(datetime.date.today())
    activate_subscriptions()

    warn_subscriptions_still_active()
    warn_subscriptions_not_active()
    warn_active_subscriptions_per_domain_not_one()
    warn_subscriptions_without_domain()

    check_credit_line_balances.delay()


@task
def check_credit_line_balances():
    for credit_line in CreditLine.objects.all():
        expected_balance = sum(credit_line.creditadjustment_set.values_list('amount', flat=True))
        if expected_balance != credit_line.balance:
            try:
                # needed for sending to sentry
                raise CreditLineBalanceMismatchError()
            except CreditLineBalanceMismatchError:
                log_accounting_error(
                    f'Credit line {credit_line.id} has balance {credit_line.balance},'
                    f' expected {expected_balance}'
                )


def generate_invoices_based_on_date(invoice_date):
    invoice_start, invoice_end = get_previous_month_date_range(invoice_date)
    log_accounting_info("Starting up invoices for %(start)s - %(end)s" % {
        'start': invoice_start.strftime(USER_DATE_FORMAT),
        'end': invoice_end.strftime(USER_DATE_FORMAT),
    })
    all_domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
    for domain_doc in iter_docs(Domain.get_db(), all_domain_ids):
        domain_obj = Domain.wrap(domain_doc)
        if not domain_obj.is_active:
            continue
        try:
            invoice_factory = DomainInvoiceFactory(invoice_start, invoice_end, domain_obj)
            invoice_factory.create_invoices()
            log_accounting_info("Sent invoices for domain %s" % domain_obj.name)
        except CreditLineError as e:
            log_accounting_error(
                "There was an error utilizing credits for "
                "domain %s: %s" % (domain_obj.name, e),
                show_stack_trace=True,
            )
        except InvoiceError as e:
            log_accounting_error(
                "Could not create invoice for domain %s: %s" % (domain_obj.name, e),
                show_stack_trace=True,
            )
        except Exception as e:
            log_accounting_error(
                "Error occurred while creating invoice for "
                "domain %s: %s" % (domain_obj.name, e),
                show_stack_trace=True,
            )
    all_customer_billing_accounts = BillingAccount.objects.filter(is_customer_billing_account=True)
    for account in all_customer_billing_accounts:
        try:
            if account.invoicing_plan == InvoicingPlan.QUARTERLY:
                customer_invoice_start = invoice_start - relativedelta(months=2)
            elif account.invoicing_plan == InvoicingPlan.YEARLY:
                customer_invoice_start = invoice_start - relativedelta(months=11)
            else:
                customer_invoice_start = invoice_start
            invoice_factory = CustomerAccountInvoiceFactory(
                account=account,
                date_start=customer_invoice_start,
                date_end=invoice_end
            )
            invoice_factory.create_invoice()
        except CreditLineError as e:
            log_accounting_error(
                "There was an error utilizing credits for "
                "domain %s: %s" % (domain_obj.name, e),
                show_stack_trace=True,
            )
        except InvoiceError as e:
            log_accounting_error(
                "Could not create invoice for domain %s: %s" % (domain_obj.name, e),
                show_stack_trace=True,
            )
        except Exception as e:
            log_accounting_error(
                "Error occurred while creating invoice for "
                "domain %s: %s" % (domain_obj.name, e),
                show_stack_trace=True,
            )

    if not settings.UNIT_TESTING:
        _invoicing_complete_soft_assert(False, "Invoicing is complete!")


@periodic_task(run_every=crontab(hour=13, minute=0, day_of_month='1'), acks_late=True)
def generate_invoices():
    """
    Generates all invoices for the past month.
    """
    invoice_date = datetime.date.today()
    generate_invoices_based_on_date(invoice_date)


def send_bookkeeper_email(month=None, year=None, emails=None):
    today = datetime.date.today()

    # now, make sure that we send out LAST month's invoices if we did
    # not specify a month or year.
    today = get_previous_month_date_range(today)[0]

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
        'accounting/email/bookkeeper.html', email_context)
    email_content_plaintext = render_to_string(
        'accounting/email/bookkeeper.txt', email_context)

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


@periodic_task(run_every=crontab(minute=0, hour=0), acks_late=True)
def remind_subscription_ending():
    """
    Sends reminder emails for subscriptions ending N days from now.
    """
    send_subscription_reminder_emails(30)
    send_subscription_reminder_emails(10)
    send_subscription_reminder_emails(1)


@periodic_task(run_every=crontab(minute=0, hour=0), acks_late=True)
def remind_dimagi_contact_subscription_ending_60_days():
    """
    Sends reminder emails to Dimagi contacts that subscriptions are ending in 60 days
    """
    send_subscription_reminder_emails_dimagi_contact(60)


def send_subscription_reminder_emails(num_days):
    today = datetime.date.today()
    date_in_n_days = today + datetime.timedelta(days=num_days)
    ending_subscriptions = Subscription.visible_objects.filter(
        date_end=date_in_n_days, do_not_email_reminder=False, is_trial=False
    )
    for subscription in ending_subscriptions:
        try:
            # only send reminder emails if the subscription isn't renewed
            if not subscription.is_renewed:
                subscription.send_ending_reminder_email()
        except Exception as e:
            log_accounting_error(
                "Error sending reminder for subscription %d: %s" % (subscription.id, str(e)),
                show_stack_trace=True,
            )


def send_subscription_reminder_emails_dimagi_contact(num_days):
    today = datetime.date.today()
    date_in_n_days = today + datetime.timedelta(days=num_days)
    ending_subscriptions = (Subscription.visible_objects
                            .filter(is_active=True)
                            .filter(date_end=date_in_n_days)
                            .filter(do_not_email_reminder=False)
                            .exclude(account__dimagi_contact=''))
    for subscription in ending_subscriptions:
        # only send reminder emails if the subscription isn't renewed
        if not subscription.is_renewed:
            subscription.send_dimagi_ending_reminder_email()


@task(ignore_result=True, acks_late=True)
@transaction.atomic()
def create_wire_credits_invoice(domain_name,
                                amount,
                                invoice_items,
                                contact_emails):
    deserialized_amount = deserialize_decimal(amount)
    wire_invoice = WirePrepaymentInvoice.objects.create(
        domain=domain_name,
        date_start=datetime.datetime.utcnow(),
        date_end=datetime.datetime.utcnow(),
        date_due=None,
        balance=deserialized_amount,
    )

    deserialized_items = []
    for item in invoice_items:
        general_credit_amount = item['amount']
        deserialized_general_credit = deserialize_decimal(general_credit_amount)
        deserialized_items.append({'type': item['type'], 'amount': deserialized_general_credit})

    wire_invoice.items = deserialized_items

    record = WirePrepaymentBillingRecord.generate_record(wire_invoice)
    if record.should_send_email:
        try:
            for email in contact_emails:
                record.send_email(contact_email=email)
        except Exception as e:
            log_accounting_error(
                "Error sending email for WirePrepaymentBillingRecord %d: %s" % (record.id, str(e)),
                show_stack_trace=True,
            )
    else:
        record.skipped_email = True
        record.save()


@task(ignore_result=True, acks_late=True)
def send_purchase_receipt(payment_record_id, domain, template_html, template_plaintext, additional_context):
    context = get_context_to_send_purchase_receipt(payment_record_id, domain, additional_context)

    email_html = render_to_string(template_html, context['template_context'])
    email_plaintext = render_to_string(template_plaintext, context['template_context'])

    send_HTML_email(
        subject=_("Payment Received - Thank You!"),
        recipient=context['email_to'],
        html_content=email_html,
        text_content=email_plaintext,
        email_from=context['email_from'],
    )


@task(queue='background_queue', ignore_result=True, acks_late=True)
def send_autopay_failed(invoice_id):
    context = get_context_to_send_autopay_failed_email(invoice_id)

    template_html = 'accounting/email/autopay_failed.html'
    html_content = render_to_string(template_html, context['template_context'])

    template_plaintext = 'accounting/email/autopay_failed.txt'
    text_content = render_to_string(template_plaintext, context['template_context'])

    send_HTML_email(
        subject=_(f"Subscription Payment for CommCare Invoice {context['invoice_number']} was declined"),
        recipient=context['email_to'],
        html_content=html_content,
        text_content=text_content,
        email_from=context['email_from'],
    )


# Email this out every Monday morning.
@periodic_task(run_every=crontab(minute=0, hour=0, day_of_week=1), acks_late=True)
def weekly_digest():
    today = datetime.date.today()
    in_forty_days = today + datetime.timedelta(days=40)

    ending_in_forty_days = [sub for sub in Subscription.visible_objects.filter(
        date_end__lte=in_forty_days,
        date_end__gte=today,
        is_active=True,
        is_trial=False,
    ).exclude(
        account__dimagi_contact='',
    ) if not sub.is_renewed]

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

    file_to_attach = io.BytesIO()
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
        'accounting/email/digest.html', email_context)
    email_content_plaintext = render_to_string(
        'accounting/email/digest.txt', email_context)

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


@periodic_task(run_every=crontab(hour=1, minute=0,), acks_late=True)
def pay_autopay_invoices():
    """ Check for autopayable invoices every day and pay them """
    AutoPayInvoicePaymentHandler().pay_autopayable_invoices(datetime.datetime.today())


@periodic_task(run_every=crontab(minute=0, hour=0), queue='background_queue', acks_late=True)
def update_exchange_rates():
    app_id = settings.OPEN_EXCHANGE_RATES_API_ID
    if app_id:
        try:
            log_accounting_info("Updating exchange rates...")
            rates = json.load(six.moves.urllib.request.urlopen(
                'https://openexchangerates.org/api/latest.json?app_id=%s' % app_id))['rates']
            default_rate = float(rates[Currency.get_default().code])
            for code, rate in rates.items():
                currency, _ = Currency.objects.get_or_create(code=code)
                currency.rate_to_default = float(rate) / default_rate
                currency.save()
                log_accounting_info("Exchange rate for %(code)s updated %(rate)f." % {
                    'code': currency.code,
                    'rate': currency.rate_to_default,
                })
        except Exception as e:
            log_accounting_error(
                "Error updating exchange rates: %s" % str(e),
                show_stack_trace=True,
            )


# Email this out on the first day and first hour of each month
@periodic_task(run_every=crontab(minute=0, hour=0, day_of_month=1), acks_late=True)
def send_credits_on_hq_report():
    if settings.SAAS_REPORTING_EMAIL and settings.SERVER_ENVIRONMENT in [
        'production',
        'india',
        'swiss'
    ]:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        credits_report = CreditsAutomatedReport()
        credits_report.send_report(settings.SAAS_REPORTING_EMAIL)
        log_accounting_info("Sent credits on hq report as of {}".format(
            yesterday.isoformat()))


@periodic_task(run_every=crontab(minute=0, hour=9), queue='background_queue', acks_late=True)
def run_downgrade_process():
    downgrade_eligible_domains()


@task(queue='background_queue', ignore_result=True, acks_late=True,
      default_retry_delay=10, max_retries=10, bind=True)
def archive_logos(self, domain_name):
    try:
        for app in get_all_apps(domain_name):
            if isinstance(app, ApplicationMediaMixin):
                has_archived = app.archive_logos()
                if has_archived:
                    app.save()
    except ResourceConflict as e:
        raise self.retry(exc=e)
    except Exception as e:
        log_accounting_error(
            "Failed to remove all commcare logos for domain %s." % domain_name,
            show_stack_trace=True,
        )
        raise e


@task(queue='background_queue', ignore_result=True, acks_late=True,
      default_retry_delay=10, max_retries=10, bind=True)
def restore_logos(self, domain_name):
    try:
        for app in get_all_apps(domain_name):
            if isinstance(app, ApplicationMediaMixin):
                has_restored = app.restore_logos()
                if has_restored:
                    app.save()
    except ResourceConflict as e:
        raise self.retry(exc=e)
    except Exception as e:
        log_accounting_error(
            "Failed to restore all commcare logos for domain %s." % domain_name,
            show_stack_trace=True,
        )
        raise e


@periodic_task(run_every=crontab(day_of_month='1', hour=5, minute=0), queue='background_queue', acks_late=True)
def send_prepaid_credits_export():
    if settings.ENTERPRISE_MODE:
        return

    headers = [
        'Account Name', 'Project Space', 'Edition', 'Start Date', 'End Date',
        '# General Credits', '# Product Credits', '# User Credits', '# SMS Credits', 'Last Date Modified'
    ]

    body = []
    for subscription in Subscription.visible_objects.filter(
        service_type=SubscriptionType.PRODUCT,
    ).order_by('subscriber__domain', 'id'):
        general_credit_lines = CreditLine.get_credits_by_subscription_and_features(subscription)
        product_credit_lines = CreditLine.get_credits_by_subscription_and_features(subscription, is_product=True)
        user_credit_lines = CreditLine.get_credits_by_subscription_and_features(
            subscription, feature_type=FeatureType.USER)
        sms_credit_lines = CreditLine.get_credits_by_subscription_and_features(
            subscription, feature_type=FeatureType.SMS)
        all_credit_lines = general_credit_lines | product_credit_lines | user_credit_lines | sms_credit_lines

        body.append([
            subscription.account.name, subscription.subscriber.domain, subscription.plan_version.plan.edition,
            subscription.date_start, subscription.date_end,
            sum(credit_line.balance for credit_line in general_credit_lines),
            sum(credit_line.balance for credit_line in product_credit_lines),
            sum(credit_line.balance for credit_line in user_credit_lines),
            sum(credit_line.balance for credit_line in sms_credit_lines),
            max(
                credit_line.last_modified for credit_line in all_credit_lines
            ).strftime(SERVER_DATETIME_FORMAT_NO_SEC)
            if all_credit_lines else 'N/A',
        ])

    for account in BillingAccount.objects.order_by('name', 'id'):
        general_credit_lines = CreditLine.get_credits_for_account(account)
        product_credit_lines = CreditLine.get_credits_for_account(account, is_product=True)
        user_credit_lines = CreditLine.get_credits_for_account(account, feature_type=FeatureType.USER)
        sms_credit_lines = CreditLine.get_credits_for_account(account, feature_type=FeatureType.SMS)
        all_credit_lines = general_credit_lines | product_credit_lines | user_credit_lines | sms_credit_lines

        body.append([
            account.name, '', '', '', '',
            sum(credit_line.balance for credit_line in general_credit_lines),
            sum(credit_line.balance for credit_line in product_credit_lines),
            sum(credit_line.balance for credit_line in user_credit_lines),
            sum(credit_line.balance for credit_line in sms_credit_lines),
            max(
                credit_line.last_modified for credit_line in all_credit_lines
            ).strftime(SERVER_DATETIME_FORMAT_NO_SEC)
            if all_credit_lines else 'N/A',
        ])

    file_obj = io.StringIO()
    writer = csv.writer(file_obj)
    writer.writerow(headers)
    for row in body:
        writer.writerow([
            val if isinstance(val, str) else bytes(val)
            for val in row
        ])

    date_string = datetime.datetime.utcnow().strftime(SERVER_DATE_FORMAT)
    filename = 'prepaid-credits-export_%s_%s.csv' % (settings.SERVER_ENVIRONMENT, date_string)
    send_HTML_email(
        '[%s] Prepaid Credits Export - %s' % (settings.SERVER_ENVIRONMENT, date_string),
        settings.ACCOUNTS_EMAIL,
        'See attached file.',
        file_attachments=[{'file_obj': file_obj, 'title': filename, 'mimetype': 'text/csv'}],
    )


@periodic_task(run_every=crontab(hour=1, minute=0, day_of_month='1'), acks_late=True)
def calculate_users_in_all_domains(today=None):
    today = today or datetime.date.today()
    for domain in Domain.get_all_names():
        num_users = CommCareUser.total_by_domain(domain)
        record_date = today - relativedelta(days=1)
        try:
            DomainUserHistory.objects.create(
                domain=domain,
                num_users=num_users,
                record_date=record_date
            )
        except Exception as e:
            log_accounting_error(
                "Something went wrong while creating DomainUserHistory for domain %s: %s" % (domain, e),
                show_stack_trace=True,
            )
    # kick off the auto-deactivation of mobile workers after we calculate the
    # DomainUserHistory for projects. This ensures this feature is never abused
    # to get around our billing system.
    from corehq.apps.enterprise.tasks import auto_deactivate_mobile_workers
    auto_deactivate_mobile_workers.delay()


@periodic_task(run_every=crontab(hour=1, minute=0, day_of_month='1'), acks_late=True)
def calculate_web_users_in_all_billing_accounts(today=None):
    today = today or datetime.date.today()
    for account in BillingAccount.objects.all():
        record_date = today - relativedelta(days=1)
        num_users = account.get_web_user_count()
        try:
            BillingAccountWebUserHistory.objects.create(
                billing_account=account,
                num_users=num_users,
                record_date=record_date
            )
        except Exception as e:
            log_accounting_error(
                f"Unable to create BillingAccountWebUserHistory for account {account.name}: {e}",
                show_stack_trace=True,
            )
