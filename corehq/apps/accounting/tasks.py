from __future__ import absolute_import
from __future__ import division
import csv
import datetime
import io
import json
import six.moves.urllib.request, six.moves.urllib.error, six.moves.urllib.parse
from six.moves.urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpRequest, QueryDict
from django.template.loader import render_to_string
from django.utils.translation import ugettext

from couchdbkit import ResourceConflict
from celery.schedules import crontab
from celery.task import periodic_task, task

from couchexport.export import export_from_tables
from couchexport.models import Format
from dimagi.utils.couch.database import iter_docs
from corehq.util.log import send_HTML_email

from corehq.apps.accounting.exceptions import (
    CreditLineError,
    InvoiceError,
)
from corehq.apps.accounting.invoicing import DomainInvoiceFactory
from corehq.apps.accounting.models import (
    BillingAccount,
    CreditLine,
    Currency,
    DefaultProductPlan,
    EntryPoint,
    FeatureType,
    Invoice,
    SoftwarePlanEdition,
    StripePaymentMethod,
    Subscription,
    SubscriptionAdjustment,
    SubscriptionAdjustmentMethod,
    SubscriptionAdjustmentReason,
    SubscriptionType,
    WirePrepaymentBillingRecord,
    WirePrepaymentInvoice,
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
from corehq.apps.domain.models import Domain
from corehq.apps.hqmedia.models import HQMediaMixin
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.notifications.models import Notification
from corehq.apps.users.models import FakeUser, WebUser
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
        is_active=False,
    )
    if based_on_date:
        starting_subscriptions = starting_subscriptions.filter(date_start=based_on_date)
    else:
        today = datetime.date.today()
        starting_subscriptions = starting_subscriptions.filter(
            Q(date_end__isnull=True) | Q(date_end__gt=today),
            date_start__lte=today,
        )

    for subscription in starting_subscriptions:
        try:
            _activate_subscription(subscription)
        except Exception as e:
            log_accounting_error(
                'Error activating subscription %d: %s' % (subscription.id, e.message),
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
        next_subscription = assign_explicit_community_subscription(
            subscription.subscriber.domain, subscription.date_end, account=subscription.account
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
                'Error deactivating subscription %d: %s' % (subscription.id, e.message),
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
        elif active_subscription_count == 0:
            log_accounting_error("There is no active subscription for domain %s" % domain_name)


@periodic_task(run_every=crontab(minute=0, hour=5), acks_late=True)
def update_subscriptions():
    deactivate_subscriptions(datetime.date.today())
    deactivate_subscriptions()
    activate_subscriptions(datetime.date.today())
    activate_subscriptions()

    warn_subscriptions_still_active()
    warn_subscriptions_not_active()
    warn_active_subscriptions_per_domain_not_one()


@periodic_task(run_every=crontab(hour=13, minute=0, day_of_month='1'), acks_late=True)
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
        domain = Domain.wrap(domain_doc)
        try:
            invoice_factory = DomainInvoiceFactory(
                invoice_start, invoice_end, domain)
            invoice_factory.create_invoices()
            log_accounting_info("Sent invoices for domain %s" % domain.name)
        except CreditLineError as e:
            log_accounting_error(
                "There was an error utilizing credits for "
                "domain %s: %s" % (domain.name, e),
                show_stack_trace=True,
            )
        except InvoiceError as e:
            log_accounting_error(
                "Could not create invoice for domain %s: %s" % (domain.name, e),
                show_stack_trace=True,
            )
        except Exception as e:
            log_accounting_error(
                "Error occurred while creating invoice for "
                "domain %s: %s" % (domain.name, e),
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
                "Error sending reminder for subscription %d: %s" % (subscription.id, e.message),
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
                                account_created_by,
                                account_entry_point,
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
            record.send_email(contact_emails=contact_emails)
        except Exception as e:
            log_accounting_error(
                "Error sending email for WirePrepaymentBillingRecord %d: %s" % (record.id, e.message),
                show_stack_trace=True,
            )
    else:
        record.skipped_email = True
        record.save()


@task(ignore_result=True, acks_late=True)
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
        ugettext("Payment Received - Thank You!"), email, email_html,
        text_content=email_plaintext,
        email_from=get_dimagi_from_email(),
    )


@task(queue='background_queue', ignore_result=True, acks_late=True)
def send_autopay_failed(invoice, payment_method):
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

    template_html = 'accounting/autopay_failed_email.html'
    template_plaintext = 'accounting/autopay_failed_email.txt'

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


@periodic_task(run_every=crontab(hour=1, minute=0,), acks_late=True)
def pay_autopay_invoices():
    """ Check for autopayable invoices every day and pay them """
    AutoPayInvoicePaymentHandler().pay_autopayable_invoices(datetime.datetime.today())


@periodic_task(run_every=crontab(minute=0, hour=0), queue='background_queue', acks_late=True)
def update_exchange_rates(app_id=settings.OPEN_EXCHANGE_RATES_API_ID):
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
                "Error updating exchange rates: %s" % e.message,
                show_stack_trace=True,
            )


def ensure_explicit_community_subscription(domain_name, from_date):
    if not Subscription.visible_objects.filter(
        Q(date_end__gt=from_date) | Q(date_end__isnull=True),
        date_start__lte=from_date,
        subscriber__domain=domain_name,
    ).exists():
        assign_explicit_community_subscription(domain_name, from_date)


def assign_explicit_community_subscription(domain_name, start_date, account=None):
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
        adjustment_method=SubscriptionAdjustmentMethod.TASK,
        internal_change=True,
        service_type=SubscriptionType.PRODUCT,
    )


@periodic_task(run_every=crontab(minute=0, hour=9), queue='background_queue', acks_late=True)
def send_overdue_reminders(today=None):
    from corehq.apps.domain.views import DomainSubscriptionView
    from corehq.apps.domain.views import DomainBillingStatementsView

    today = today or datetime.date.today()
    invoices = Invoice.objects.filter(is_hidden=False,
                                      subscription__service_type=SubscriptionType.PRODUCT,
                                      date_paid__isnull=True,
                                      date_due__lt=today)\
        .exclude(subscription__plan_version__plan__edition=SoftwarePlanEdition.ENTERPRISE)\
        .order_by('date_due')\
        .select_related('subscription__subscriber')

    domains = set()
    for invoice in invoices:
        if invoice.get_domain() not in domains:
            domains.add(invoice.get_domain())
            total = Invoice.objects.filter(is_hidden=False,
                                           subscription__subscriber__domain=invoice.get_domain())\
                .aggregate(Sum('balance'))['balance__sum']
            if total >= 100:
                domain = Domain.get_by_name(invoice.get_domain())
                current_subscription = Subscription.get_active_subscription_by_domain(domain.name)
                if (
                    current_subscription.plan_version.plan.edition != SoftwarePlanEdition.COMMUNITY
                    and not current_subscription.skip_auto_downgrade
                ):
                    days_ago = (today - invoice.date_due).days
                    context = {
                        'domain': invoice.get_domain(),
                        'total': total,
                        'subscription_url': absolute_reverse(DomainSubscriptionView.urlname,
                                                             args=[invoice.get_domain()]),
                        'statements_url': absolute_reverse(DomainBillingStatementsView.urlname,
                                                           args=[invoice.get_domain()]),
                        'date_60': invoice.date_due + datetime.timedelta(days=60),
                        'contact_email': settings.INVOICING_CONTACT_EMAIL
                    }
                    if days_ago == 61:
                        _downgrade_domain(current_subscription)
                        _send_downgrade_notice(invoice, context)
                    elif days_ago == 58:
                        _send_downgrade_warning(invoice, context)
                    elif days_ago == 30:
                        _send_overdue_notice(invoice, context)
                    elif days_ago == 1:
                        _create_overdue_notification(invoice, context)


def _send_downgrade_notice(invoice, context):
    send_html_email_async.delay(
        ugettext('Oh no! Your CommCare subscription for {} has been downgraded'.format(invoice.get_domain())),
        invoice.contact_emails,
        render_to_string('accounting/downgrade.html', context),
        render_to_string('accounting/downgrade.txt', context),
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
    send_html_email_async.delay(
        ugettext("CommCare Alert: {}'s subscription will be downgraded to Community Plan after tomorrow!".format(
            invoice.get_domain()
        )),
        invoice.contact_emails,
        render_to_string('accounting/downgrade_warning.html', context),
        render_to_string('accounting/downgrade_warning.txt', context),
        cc=[settings.ACCOUNTS_EMAIL],
        bcc=[settings.GROWTH_EMAIL],
        email_from=get_dimagi_from_email())


def _send_overdue_notice(invoice, context):
    send_html_email_async.delay(
        ugettext('CommCare Billing Statement 30 days Overdue for {}'.format(invoice.get_domain())),
        invoice.contact_emails,
        render_to_string('accounting/30_days.html', context),
        render_to_string('accounting/30_days.txt', context),
        cc=[settings.ACCOUNTS_EMAIL],
        bcc=[settings.GROWTH_EMAIL],
        email_from=get_dimagi_from_email())


def _create_overdue_notification(invoice, context):
    message = ugettext('Reminder - your {} statement is past due!'.format(
        invoice.date_start.strftime('%B')
    ))
    note = Notification.objects.create(content=message, url=context['statements_url'],
                                       domain_specific=True, type='billing',
                                       domains=[invoice.get_domain()])
    note.activate()


@task(queue='background_queue', ignore_result=True, acks_late=True,
      default_retry_delay=10, max_retries=10, bind=True)
def archive_logos(self, domain_name):
    try:
        for app in get_all_apps(domain_name):
            if isinstance(app, HQMediaMixin):
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
            if isinstance(app, HQMediaMixin):
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


@periodic_task(run_every=crontab(day_of_month=1, hour=5), queue='background_queue', acks_late=True)
def send_prepaid_credits_export():
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

    file_obj = io.BytesIO()
    writer = csv.writer(file_obj)
    writer.writerow(headers)
    for row in body:
        writer.writerow([
            val.encode('utf-8') if isinstance(val, six.text_type) else six.binary_type(val)
            for val in row
        ])

    date_string = datetime.datetime.utcnow().strftime(SERVER_DATE_FORMAT)
    filename = datetime.datetime.utcnow().strftime('prepaid-credits-export_%s.csv' % date_string)
    send_HTML_email(
        'Prepaid Credits Export - %s' % date_string, settings.ACCOUNTS_EMAIL, 'See attached file.',
        file_attachments=[{'file_obj': file_obj, 'title': filename, 'mimetype': 'text/csv'}],
    )
