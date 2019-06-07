from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import csv342 as csv
import datetime
from datetime import date
import io
import json
import uuid
import six.moves.urllib.request, six.moves.urllib.error, six.moves.urllib.parse
from six.moves.urllib.parse import urlencode
from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import HttpRequest, QueryDict
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from couchdbkit import ResourceConflict
from celery.schedules import crontab
from celery.task import periodic_task, task

from couchexport.export import export_from_tables
from couchexport.models import Format
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch.database import iter_docs
from corehq.util.log import send_HTML_email

from corehq.apps.accounting.enterprise import EnterpriseReport
from corehq.apps.accounting.exceptions import (
    CreditLineError,
    InvoiceError,
)
from corehq.apps.accounting.invoicing import DomainInvoiceFactory, CustomerAccountInvoiceFactory
from corehq.apps.accounting.models import (
    BillingAccount,
    CreditLine,
    Currency,
    DefaultProductPlan,
    EntryPoint,
    FeatureType,
    Invoice,
    CustomerInvoice,
    SoftwarePlanEdition,
    StripePaymentMethod,
    Subscription,
    SubscriptionAdjustment,
    SubscriptionAdjustmentMethod,
    SubscriptionAdjustmentReason,
    SubscriptionType,
    WirePrepaymentBillingRecord,
    WirePrepaymentInvoice,
    DomainUserHistory,
    InvoicingPlan
)
from corehq.apps.accounting.payment_handlers import AutoPayInvoicePaymentHandler
from corehq.apps.accounting.utils import (
    fmt_dollar_amount,
    get_change_status,
    get_dimagi_from_email,
    log_accounting_error,
    log_accounting_info,
)
from corehq.apps.app_manager.dbaccessors import get_all_apps
from corehq.const import ONE_DAY
from corehq.apps.domain.models import Domain
from corehq.apps.hqmedia.models import ApplicationMediaMixin
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import FakeUser, WebUser, CommCareUser
from corehq.const import (
    SERVER_DATE_FORMAT,
    SERVER_DATETIME_FORMAT_NO_SEC,
    USER_DATE_FORMAT,
    USER_MONTH_FORMAT,
)
from corehq.util.view_utils import absolute_reverse
from corehq.util.dates import get_previous_month_date_range
from corehq.util.soft_assert import soft_assert

_invoicing_complete_soft_assert = soft_assert(
    to='{}@{}'.format('npellegrino', 'dimagi.com'),
    exponential_backoff=False,
)

UNPAID_INVOICE_THRESHOLD = 100


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
                'Error activating subscription %d: %s' % (subscription.id, six.text_type(e)),
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
                domain, created_by='default_community_after_customer_level'
            )
        next_subscription = assign_explicit_community_subscription(
            domain, subscription.date_end, SubscriptionAdjustmentMethod.DEFAULT_COMMUNITY, account=account
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
                'Error deactivating subscription %d: %s' % (subscription.id, six.text_type(e)),
                show_stack_trace=True,
            )


def warn_subscriptions_still_active(based_on_date=None):
    ending_date = based_on_date or datetime.date.today()
    subscriptions_still_active = Subscription.visible_objects.filter(
        date_end__lte=ending_date,
        is_active=True,
    )
    for subscription in subscriptions_still_active:
        log_accounting_error("%s is still active." % subscription)


def warn_subscriptions_not_active(based_on_date=None):
    based_on_date = based_on_date or datetime.date.today()
    subscriptions_not_active = Subscription.visible_objects.filter(
        Q(date_end=None) | Q(date_end__gt=based_on_date),
        date_start__lte=based_on_date,
        is_active=False,
    )
    for subscription in subscriptions_not_active:
        log_accounting_error("%s is not active" % subscription)


def warn_active_subscriptions_per_domain_not_one():
    for domain_name in Domain.get_all_names():
        active_subscription_count = Subscription.visible_objects.filter(
            subscriber__domain=domain_name,
            is_active=True,
        ).count()
        if active_subscription_count > 1:
            log_accounting_error("Multiple active subscriptions found for domain %s" % domain_name)
        elif active_subscription_count == 0 and Domain.get_by_name(domain_name).is_active:
            log_accounting_error("There is no active subscription for domain %s" % domain_name)


def warn_subscriptions_without_domain():
    domains_with_active_subscription = Subscription.visible_objects.filter(
        is_active=True,
    ).values_list('subscriber__domain', flat=True).distinct()
    for domain_name in set(domains_with_active_subscription) - set(Domain.get_all_names()):
        log_accounting_error('Domain %s has an active subscription but does not exist.' % domain_name)


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
            log_accounting_error(
                'Credit line %s has balance %s, expected %s' % (credit_line.id, credit_line.balance, expected_balance)
            )


@periodic_task(serializer='pickle', run_every=crontab(hour=13, minute=0, day_of_month='1'), acks_late=True)
def generate_invoices(based_on_date=None):
    """
    Generates all invoices for the past month.
    """
    today = based_on_date or datetime.date.today()
    invoice_start, invoice_end = get_previous_month_date_range(today)
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
                "Error sending reminder for subscription %d: %s" % (subscription.id, six.text_type(e)),
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


@task(serializer='pickle', ignore_result=True, acks_late=True)
@transaction.atomic()
def create_wire_credits_invoice(domain_name,
                                amount,
                                invoice_items,
                                contact_emails):
    wire_invoice = WirePrepaymentInvoice.objects.create(
        domain=domain_name,
        date_start=datetime.datetime.utcnow(),
        date_end=datetime.datetime.utcnow(),
        date_due=None,
        balance=amount,
    )
    wire_invoice.items = invoice_items

    record = WirePrepaymentBillingRecord.generate_record(wire_invoice)
    if record.should_send_email:
        try:
            for email in contact_emails:
                record.send_email(contact_email=email)
        except Exception as e:
            log_accounting_error(
                "Error sending email for WirePrepaymentBillingRecord %d: %s" % (record.id, six.text_type(e)),
                show_stack_trace=True,
            )
    else:
        record.skipped_email = True
        record.save()


@task(serializer='pickle', ignore_result=True, acks_late=True)
def send_purchase_receipt(payment_record, domain,
                          template_html, template_plaintext,
                          additional_context):
    username = payment_record.payment_method.web_user
    web_user = WebUser.get_by_username(username)
    if web_user:
        email = web_user.get_email()
        name = web_user.first_name
    else:
        log_accounting_error(
            "Strange. A payment attempt was made by a user that "
            "we can't seem to find! %s" % username,
            show_stack_trace=True,
        )
        name = email = username

    context = {
        'name': name,
        'amount': fmt_dollar_amount(payment_record.amount),
        'project': domain,
        'date_paid': payment_record.date_created.strftime(USER_DATE_FORMAT),
        'transaction_id': payment_record.public_transaction_id,
    }
    context.update(additional_context)

    email_html = render_to_string(template_html, context)
    email_plaintext = render_to_string(template_plaintext, context)

    send_HTML_email(
        _("Payment Received - Thank You!"), email, email_html,
        text_content=email_plaintext,
        email_from=get_dimagi_from_email(),
    )


@task(serializer='pickle', queue='background_queue', ignore_result=True, acks_late=True)
def send_autopay_failed(invoice):
    subscription = invoice.subscription
    auto_payer = subscription.account.auto_pay_user
    payment_method = StripePaymentMethod.objects.get(web_user=auto_payer)
    autopay_card = payment_method.get_autopay_card(subscription.account)
    web_user = WebUser.get_by_username(auto_payer)
    if web_user:
        recipient = web_user.get_email()
    else:
        recipient = auto_payer
    domain = invoice.get_domain()

    context = {
        'domain': domain,
        'subscription_plan': subscription.plan_version.plan.name,
        'billing_date': datetime.date.today(),
        'invoice_number': invoice.invoice_number,
        'autopay_card': autopay_card,
        'domain_url': absolute_reverse('dashboard_default', args=[domain]),
        'billing_info_url': absolute_reverse('domain_update_billing_info', args=[domain]),
        'support_email': settings.INVOICING_CONTACT_EMAIL,
    }

    template_html = 'accounting/email/autopay_failed.html'
    template_plaintext = 'accounting/email/autopay_failed.txt'

    send_HTML_email(
        subject="Subscription Payment for CommCare Invoice %s was declined" % invoice.invoice_number,
        recipient=recipient,
        html_content=render_to_string(template_html, context),
        text_content=render_to_string(template_plaintext, context),
        email_from=get_dimagi_from_email(),
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
                "Error updating exchange rates: %s" % six.text_type(e),
                show_stack_trace=True,
            )


def ensure_explicit_community_subscription(domain_name, from_date, method, web_user=None):
    if not Subscription.visible_objects.filter(
        Q(date_end__gt=from_date) | Q(date_end__isnull=True),
        date_start__lte=from_date,
        subscriber__domain=domain_name,
    ).exists():
        assign_explicit_community_subscription(domain_name, from_date, method, web_user=web_user)


def assign_explicit_community_subscription(domain_name, start_date, method, account=None, web_user=None):
    future_subscriptions = Subscription.visible_objects.filter(
        date_start__gt=start_date,
        subscriber__domain=domain_name,
    )
    if future_subscriptions.exists():
        end_date = future_subscriptions.earliest('date_start').date_start
    else:
        end_date = None

    if account is None:
        account = BillingAccount.get_or_create_account_by_domain(
            domain_name,
            created_by='assign_explicit_community_subscriptions',
            entry_point=EntryPoint.SELF_STARTED,
        )[0]

    return Subscription.new_domain_subscription(
        account=account,
        domain=domain_name,
        plan_version=DefaultProductPlan.get_default_plan_version(),
        date_start=start_date,
        date_end=end_date,
        skip_invoicing_if_no_feature_charges=True,
        adjustment_method=method,
        internal_change=True,
        service_type=SubscriptionType.PRODUCT,
        web_user=web_user,
    )


@periodic_task(run_every=crontab(minute=0, hour=9), queue='background_queue', acks_late=True)
def run_downgrade_process():
    today = datetime.date.today()

    for domain, oldest_unpaid_invoice, total in _get_domains_with_subscription_invoices_over_threshold(today):
        current_subscription = Subscription.get_active_subscription_by_domain(domain)
        if is_subscription_eligible_for_downgrade_process(current_subscription):
            _apply_downgrade_process(oldest_unpaid_invoice, total, today, current_subscription)

    for oldest_unpaid_invoice, total in get_accounts_with_customer_invoices_over_threshold(today):
        subscription_on_invoice = oldest_unpaid_invoice.subscriptions.first()
        if is_subscription_eligible_for_downgrade_process(subscription_on_invoice):
            _apply_downgrade_process(oldest_unpaid_invoice, total, today)


def _get_domains_with_subscription_invoices_over_threshold(today):
    for domain in set(_get_unpaid_saas_invoices_in_downgrade_daterange(today).values_list(
        'subscription__subscriber__domain', flat=True
    )):
        overdue_invoice, total_overdue_to_date = get_unpaid_invoices_over_threshold_by_domain(today, domain)
        if overdue_invoice:
            yield domain, overdue_invoice, total_overdue_to_date


def get_unpaid_invoices_over_threshold_by_domain(today, domain):
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


def _get_unpaid_saas_invoices_in_downgrade_daterange(today):
    return _get_all_unpaid_saas_invoices().filter(
        date_due__lte=today - datetime.timedelta(days=1),
        date_due__gte=today - datetime.timedelta(days=61)
    ).order_by('date_due').select_related('subscription__subscriber')


def _get_all_unpaid_saas_invoices():
    return Invoice.objects.filter(
        is_hidden=False,
        subscription__service_type=SubscriptionType.PRODUCT,
        date_paid__isnull=True,
    )


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


def is_subscription_eligible_for_downgrade_process(subscription):
    return (
        subscription.plan_version.plan.edition != SoftwarePlanEdition.COMMUNITY
        and not subscription.skip_auto_downgrade
    )


def _apply_downgrade_process(oldest_unpaid_invoice, total, today, subscription=None):
    from corehq.apps.domain.views.accounting import DomainBillingStatementsView, DomainSubscriptionView
    from corehq.apps.accounting.views import EnterpriseBillingStatementsView

    context = {
        'total': format(total, '7.2f'),
        'date_60': oldest_unpaid_invoice.date_due + datetime.timedelta(days=60),
        'contact_email': settings.INVOICING_CONTACT_EMAIL
    }
    if oldest_unpaid_invoice.is_customer_invoice:
        domain = oldest_unpaid_invoice.subscriptions.first().subscriber.domain
        context.update({
            'statements_url': absolute_reverse(
                EnterpriseBillingStatementsView.urlname, args=[domain]),
            'domain_or_account': oldest_unpaid_invoice.account.name
        })
    else:
        domain = subscription.subscriber.domain
        context.update({
            'domain': domain,
            'subscription_url': absolute_reverse(DomainSubscriptionView.urlname,
                                                 args=[domain]),
            'statements_url': absolute_reverse(DomainBillingStatementsView.urlname,
                                               args=[domain]),
            'domain_or_account': domain
        })

    days_ago = (today - oldest_unpaid_invoice.date_due).days
    if days_ago == 61:
        if not oldest_unpaid_invoice.is_customer_invoice:  # We do not automatically downgrade customer invoices
            _downgrade_domain(subscription)
            _send_downgrade_notice(oldest_unpaid_invoice, context)
    elif days_ago == 58:
        _send_downgrade_warning(oldest_unpaid_invoice, context)
    elif days_ago == 30:
        _send_overdue_notice(oldest_unpaid_invoice, context)


def _send_downgrade_notice(invoice, context):
    send_html_email_async.delay(
        _('Oh no! Your CommCare subscription for {} has been downgraded'.format(invoice.get_domain())),
        invoice.contact_emails,
        render_to_string('accounting/email/downgrade.html', context),
        render_to_string('accounting/email/downgrade.txt', context),
        cc=[settings.ACCOUNTS_EMAIL],
        bcc=[settings.GROWTH_EMAIL],
        email_from=get_dimagi_from_email()
    )


def _downgrade_domain(subscription):
    subscription.change_plan(
        DefaultProductPlan.get_default_plan_version(
            SoftwarePlanEdition.COMMUNITY
        ),
        adjustment_method=SubscriptionAdjustmentMethod.AUTOMATIC_DOWNGRADE,
        note='Automatic downgrade to community for invoice 60 days late',
        internal_change=True
    )


def _send_downgrade_warning(invoice, context):
    if invoice.is_customer_invoice:
        subject = _(
            "CommCare Alert: {}'s subscriptions will be downgraded to Community Plan after tomorrow!".format(
                invoice.account.name
            ))
        subscriptions_to_downgrade = _(
            "subscriptions on {}".format(invoice.account.name)
        )
        bcc = None
    else:
        subject = _(
            "CommCare Alert: {}'s subscription will be downgraded to Community Plan after tomorrow!".format(
                invoice.get_domain()
            ))
        subscriptions_to_downgrade = _(
            "subscription for {}".format(invoice.get_domain())
        )
        bcc = [settings.GROWTH_EMAIL]

    context.update({
        'subscriptions_to_downgrade': subscriptions_to_downgrade
    })
    send_html_email_async.delay(
        subject,
        invoice.contact_emails,
        render_to_string('accounting/email/downgrade_warning.html', context),
        render_to_string('accounting/email/downgrade_warning.txt', context),
        cc=[settings.ACCOUNTS_EMAIL],
        bcc=bcc,
        email_from=get_dimagi_from_email())


def _send_overdue_notice(invoice, context):
    if invoice.is_customer_invoice:
        bcc = None
    else:
        bcc = [settings.GROWTH_EMAIL]
    send_html_email_async.delay(
        _('CommCare Billing Statement 30 days Overdue for {}'.format(context['domain_or_account'])),
        invoice.contact_emails,
        render_to_string('accounting/email/30_days.html', context),
        render_to_string('accounting/email/30_days.txt', context),
        cc=[settings.ACCOUNTS_EMAIL],
        bcc=bcc,
        email_from=get_dimagi_from_email())


@task(serializer='pickle', queue='background_queue', ignore_result=True, acks_late=True,
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


@task(serializer='pickle', queue='background_queue', ignore_result=True, acks_late=True,
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
            val if isinstance(val, six.text_type) else bytes(val)
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


@task(serializer='pickle', queue="email_queue")
def email_enterprise_report(domain, slug, couch_user):
    account = BillingAccount.get_account_by_domain(domain)
    report = EnterpriseReport.create(slug, account.id, couch_user)

    # Generate file
    csv_file = io.StringIO()
    writer = csv.writer(csv_file)
    writer.writerow(report.headers)
    writer.writerows(report.rows)

    # Store file in redis
    hash_id = uuid.uuid4().hex
    redis = get_redis_client()
    redis.set(hash_id, csv_file.getvalue())
    redis.expire(hash_id, ONE_DAY)
    csv_file.close()

    # Send email
    url = absolute_reverse("enterprise_dashboard_download", args=[domain, report.slug, str(hash_id)])
    link = "<a href='{}'>{}</a>".format(url, url)
    subject = _("Enterprise Dashboard: {}").format(report.title)
    body = "The enterprise report you requested for the account {} is ready.<br>" \
           "You can download the data at the following link: {}<br><br>" \
           "Please remember that this link will only be active for 24 hours.".format(account.name, link)
    send_html_email_async(subject, couch_user.username, body)


@periodic_task(run_every=crontab(hour=1, minute=0, day_of_month='1'), acks_late=True)
def calculate_users_in_all_domains(today=None):
    today = today or datetime.date.today()
    for domain in Domain.get_all_names():
        num_users = CommCareUser.total_by_domain(domain)
        record_date = today - relativedelta(days=1)
        DomainUserHistory.objects.create(
            domain=domain,
            num_users=num_users,
            record_date=record_date
        )
