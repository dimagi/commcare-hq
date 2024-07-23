from datetime import date

import settings
from corehq.apps.accounting.exceptions import AccountingCommunicationError
from corehq.apps.accounting.models import (
    Invoice,
    PaymentRecord,
    StripePaymentMethod,
)
from corehq.apps.accounting.utils import (
    fmt_dollar_amount,
    get_dimagi_from_email,
    log_accounting_error,
)
from corehq.apps.users.models import WebUser
from corehq.const import USER_DATE_FORMAT
from corehq.util.view_utils import absolute_reverse


def get_context_to_send_autopay_failed_email(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    subscription = invoice.subscription
    auto_payer = subscription.account.auto_pay_user
    payment_method = StripePaymentMethod.objects.get(web_user=auto_payer)
    autopay_card = payment_method.get_autopay_card(subscription.account)
    web_user = WebUser.get_by_username(auto_payer)
    if web_user:
        recipient = web_user.get_email() if web_user.is_active else invoice.get_contact_emails()
    else:
        recipient = auto_payer
    domain = invoice.get_domain()

    template_context = {
        'domain': domain,
        'subscription_plan': subscription.plan_version.plan.name,
        'billing_date': date.today(),
        'invoice_number': invoice.invoice_number,
        'autopay_card': autopay_card,
        'domain_url': absolute_reverse('dashboard_default', args=[domain]),
        'billing_info_url': absolute_reverse('domain_update_billing_info', args=[domain]),
        'support_email': settings.INVOICING_CONTACT_EMAIL,
    }

    return {
        'template_context': template_context,
        'invoice_number': invoice.invoice_number,
        'email_to': recipient,
        'email_from': get_dimagi_from_email()
    }


def get_context_to_send_purchase_receipt(payment_record_id, domain, additional_context):
    payment_record = PaymentRecord.objects.get(id=payment_record_id)
    username = payment_record.payment_method.web_user
    web_user = WebUser.get_by_username(username)
    if web_user and web_user.is_active:
        email = web_user.get_email()
        name = web_user.first_name
    else:
        raise_except_and_log_accounting_comms_error(username)
        name = email = username

    template_context = {
        'name': name,
        'amount': fmt_dollar_amount(payment_record.amount),
        'project': domain,
        'date_paid': payment_record.date_created.strftime(USER_DATE_FORMAT),
        'transaction_id': payment_record.public_transaction_id,
    }
    template_context.update(additional_context)

    return {
        'template_context': template_context,
        'email_to': email,
        'email_from': get_dimagi_from_email()
    }


def raise_except_and_log_accounting_comms_error(username):
    try:
        # needed for sentry
        raise AccountingCommunicationError()
    except AccountingCommunicationError:
        log_accounting_error(
            f"A payment attempt was made by a user that does not exist: {username}",
            show_stack_trace=True,
        )
