import datetime

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from corehq.apps.accounting.const import (
    DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE,
    DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE_WARNING,
    DAYS_PAST_DUE_TO_TRIGGER_OVERDUE_NOTICE,
    OVERDUE_INVOICE_LIMIT_DAYS,
)
from corehq.apps.accounting.models import (
    CommunicationType,
    CustomerInvoiceCommunicationHistory,
    DefaultProductPlan,
    InvoiceCommunicationHistory,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustmentMethod,
)
from corehq.apps.accounting.utils import (
    get_dimagi_from_email,
    log_accounting_error,
)
from corehq.apps.accounting.utils.invoicing import (
    get_accounts_with_customer_invoices_overdue,
    get_domains_with_subscription_invoices_overdue,
    get_oldest_overdue_invoice_over_threshold,
)
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.util.view_utils import absolute_reverse


class Downgrade:
    @classmethod
    def run_action(cls, only_downgrade_domain=None):
        today = datetime.date.today()

        for domain, oldest_unpaid_invoice, total in get_domains_with_subscription_invoices_overdue(today):
            try:
                if only_downgrade_domain and domain != only_downgrade_domain:
                    continue
                current_subscription = Subscription.get_active_subscription_by_domain(domain)
                if (
                    current_subscription
                    and cls.is_subscription_eligible_for_downgrade_process(current_subscription)
                ):
                    cls._apply_downgrade_process(
                        oldest_unpaid_invoice, total, today, current_subscription
                    )
            except Exception:
                log_accounting_error(
                    f"There was an issue applying the downgrade process "
                    f"to {domain}.",
                    show_stack_trace=True
                )

        for oldest_unpaid_invoice, total in get_accounts_with_customer_invoices_overdue(today):
            try:
                subscription_on_invoice = oldest_unpaid_invoice.subscriptions.first()
                if only_downgrade_domain and subscription_on_invoice.subscriber.domain != only_downgrade_domain:
                    continue
                if cls.is_subscription_eligible_for_downgrade_process(subscription_on_invoice):
                    cls._apply_downgrade_process(oldest_unpaid_invoice, total, today, subscription_on_invoice)
            except Exception:
                log_accounting_error(
                    f"There was an issue applying the downgrade process "
                    f"to customer invoice {oldest_unpaid_invoice.id}.",
                    show_stack_trace=True
                )

    @classmethod
    def _apply_downgrade_process(cls, oldest_unpaid_invoice, total, today, subscription):
        domain = subscription.subscriber.domain
        communication_model, context = cls._get_communication_model_context(domain, oldest_unpaid_invoice)
        cls._check_and_perform_action(communication_model, context,
                                      oldest_unpaid_invoice, total, today, subscription)

    @staticmethod
    def _get_communication_model_context(domain, oldest_unpaid_invoice):
        from corehq.apps.domain.views.accounting import (
            DomainBillingStatementsView,
            DomainSubscriptionView,
        )
        from corehq.apps.enterprise.views import EnterpriseBillingStatementsView

        if oldest_unpaid_invoice.is_customer_invoice:
            communication_model = CustomerInvoiceCommunicationHistory
            context = {
                'statements_url': absolute_reverse(
                    EnterpriseBillingStatementsView.urlname, args=[domain]),
                'domain_or_account': oldest_unpaid_invoice.account.name
            }
        else:
            communication_model = InvoiceCommunicationHistory
            context = {
                'domain': domain,
                'subscription_url': absolute_reverse(DomainSubscriptionView.urlname,
                                                     args=[domain]),
                'statements_url': absolute_reverse(DomainBillingStatementsView.urlname,
                                                   args=[domain]),
                'domain_or_account': domain
            }
        return communication_model, context

    @staticmethod
    def is_subscription_eligible_for_downgrade_process(subscription):
        return (
            subscription.plan_version.plan.edition not in [
                SoftwarePlanEdition.COMMUNITY,
                SoftwarePlanEdition.PAUSED,
            ] and not subscription.skip_auto_downgrade
        )

    @classmethod
    def _check_and_perform_action(cls, communication_model, context,
                                  oldest_unpaid_invoice, total, today, subscription):
        context.update({
            'total': format(total, '7.2f'),
            'date_to_pause': oldest_unpaid_invoice.date_due + datetime.timedelta(days=OVERDUE_INVOICE_LIMIT_DAYS),
            'contact_email': settings.INVOICING_CONTACT_EMAIL
        })

        days_ago = (today - oldest_unpaid_invoice.date_due).days
        if cls._can_trigger_downgrade(today, days_ago, communication_model, oldest_unpaid_invoice):
            # We do not automatically downgrade customer invoices
            if not oldest_unpaid_invoice.is_customer_invoice:
                cls._downgrade_domain(subscription)
                cls._send_downgrade_notice(oldest_unpaid_invoice, context)

        elif cls._can_send_downgrade_warning(days_ago, communication_model, oldest_unpaid_invoice):
            context.update({
                'days_overdue': OVERDUE_INVOICE_LIMIT_DAYS,
            })
            cls._send_downgrade_warning(oldest_unpaid_invoice, communication_model, context)

        elif cls._can_send_overdue_notification(days_ago, communication_model, oldest_unpaid_invoice):
            context.update({
                'days_overdue': DAYS_PAST_DUE_TO_TRIGGER_OVERDUE_NOTICE,
            })
            cls._send_overdue_notice(oldest_unpaid_invoice, communication_model, context)

    @staticmethod
    def _can_trigger_downgrade(today, days_ago, communication_model, invoice):
        if days_ago < DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE:
            return False

        communication_history = communication_model.objects.filter(
            invoice=invoice,
            communication_type=CommunicationType.DOWNGRADE_WARNING,
        ).order_by('-date_created')
        if not communication_history.exists():
            # make sure we always communicate to the customer first
            return False

        # make sure we give enough time to pass after a downgrade warning
        days_since_warning = (today - communication_history.first().date_created).days
        return days_since_warning >= (
            DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE - DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE_WARNING
        )

    @staticmethod
    def _can_send_downgrade_warning(days_ago, communication_model, invoice):
        if days_ago < DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE_WARNING:
            return False
        return not communication_model.objects.filter(
            invoice=invoice,
            communication_type=CommunicationType.DOWNGRADE_WARNING,
        ).exists()

    @staticmethod
    def _can_send_overdue_notification(days_ago, communication_model, invoice):
        if days_ago < DAYS_PAST_DUE_TO_TRIGGER_OVERDUE_NOTICE:
            return False
        return not communication_model.objects.filter(
            invoice=invoice,
            communication_type=CommunicationType.OVERDUE_INVOICE,
        ).exists()

    @staticmethod
    def _downgrade_domain(subscription):
        subscription.change_plan(
            DefaultProductPlan.get_default_plan_version(
                SoftwarePlanEdition.PAUSED
            ),
            adjustment_method=SubscriptionAdjustmentMethod.AUTOMATIC_DOWNGRADE,
            note=f'Automatic pausing of subscription for invoice {OVERDUE_INVOICE_LIMIT_DAYS} days late',
            internal_change=True
        )

    @staticmethod
    def _send_downgrade_notice(invoice, context):
        send_html_email_async.delay(
            _('Oh no! Your CommCare subscription for {} has been paused'.format(invoice.get_domain())),
            invoice.get_contact_emails(include_domain_admins=True, filter_out_dimagi=True),
            render_to_string('accounting/email/downgrade.html', context),
            render_to_string('accounting/email/downgrade.txt', context),
            cc=[settings.ACCOUNTS_EMAIL],
            bcc=[settings.GROWTH_EMAIL],
            email_from=get_dimagi_from_email()
        )

    @staticmethod
    def _send_downgrade_warning(invoice, communication_model, context):
        if invoice.is_customer_invoice:
            subject = _(
                "CommCare Alert: {}'s subscriptions will be paused after tomorrow!".format(
                    invoice.account.name
                ))
            subscriptions_to_downgrade = _(
                "subscriptions on {}".format(invoice.account.name)
            )
            bcc = None
        else:
            subject = _(
                "CommCare Alert: {}'s subscription will be paused after tomorrow!".format(
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
            invoice.get_contact_emails(include_domain_admins=True, filter_out_dimagi=True),
            render_to_string('accounting/email/downgrade_warning.html', context),
            render_to_string('accounting/email/downgrade_warning.txt', context),
            cc=[settings.ACCOUNTS_EMAIL],
            bcc=bcc,
            email_from=get_dimagi_from_email())
        communication_model.objects.create(
            invoice=invoice,
            communication_type=CommunicationType.DOWNGRADE_WARNING,
        )

    @staticmethod
    def _send_overdue_notice(invoice, communication_model, context):
        if invoice.is_customer_invoice:
            bcc = None
        else:
            bcc = [settings.GROWTH_EMAIL]
        send_html_email_async.delay(
            _('CommCare Billing Statement {} days Overdue for {}'.format(
                DAYS_PAST_DUE_TO_TRIGGER_OVERDUE_NOTICE, context['domain_or_account']
            )),
            invoice.get_contact_emails(include_domain_admins=True, filter_out_dimagi=True),
            render_to_string('accounting/email/overdue_notice.html', context),
            render_to_string('accounting/email/overdue_notice.txt', context),
            cc=[settings.ACCOUNTS_EMAIL],
            bcc=bcc,
            email_from=get_dimagi_from_email()
        )
        communication_model.objects.create(
            invoice=invoice,
            communication_type=CommunicationType.OVERDUE_INVOICE,
        )


def can_domain_unpause(domain):
    today = datetime.date.today()
    oldest_unpaid_invoice = get_oldest_overdue_invoice_over_threshold(today, domain)[0]
    if not oldest_unpaid_invoice:
        return True
    days_ago = (today - oldest_unpaid_invoice.date_due).days
    return days_ago < DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE
