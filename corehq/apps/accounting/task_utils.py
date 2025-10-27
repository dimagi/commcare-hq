from datetime import date

import settings
from corehq.apps.accounting.exceptions import AccountingCommunicationError
from corehq.apps.accounting.models import (
    BillingAccount,
    CustomerInvoice,
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


def get_context_to_send_autopay_failed_email(invoice_id, is_customer_invoice=False):
    if is_customer_invoice:
        invoice = CustomerInvoice.objects.get(id=invoice_id)
        subscription_plan = None
    else:
        invoice = Invoice.objects.get(id=invoice_id)
        subscription_plan = invoice.subscription.plan_version.plan.name

    account = invoice.account
    auto_payer = account.auto_pay_user
    payment_method = StripePaymentMethod.objects.get(web_user=auto_payer)
    autopay_card = payment_method.get_autopay_card(account)
    domain_name = invoice.get_domain()
    web_user = WebUser.get_by_username(auto_payer)
    if web_user:
        if _user_active_in_domains(web_user, domain_name, account.name):
            recipient = web_user.get_email()
        else:
            recipient = invoice.get_contact_emails()
    else:
        recipient = auto_payer

    template_context = {
        'domain_or_account': domain_name or account.name,
        'billing_date': date.today(),
        'invoice_number': invoice.invoice_number,
        'autopay_card': autopay_card,
        'is_customer_invoice': is_customer_invoice,
        'subscription_plan': subscription_plan,
        'domain_url': absolute_reverse('dashboard_default', args=[domain_name]),
        'billing_info_url': absolute_reverse('domain_update_billing_info', args=[domain_name]),
        'support_email': settings.INVOICING_CONTACT_EMAIL,
    }

    return {
        'template_context': template_context,
        'invoice_number': invoice.invoice_number,
        'email_to': recipient,
        'email_from': get_dimagi_from_email()
    }


def get_context_to_send_purchase_receipt(payment_record_id, domain_name, account_name, additional_context):
    payment_record = PaymentRecord.objects.get(id=payment_record_id)
    username = payment_record.payment_method.web_user
    web_user = WebUser.get_by_username(username)
    if web_user and _user_active_in_domains(web_user, domain_name, account_name):
        email = web_user.get_email()
        name = web_user.first_name
    else:
        raise_except_and_log_accounting_comms_error(username)
        name = email = username

    template_context = {
        'name': name,
        'amount': fmt_dollar_amount(payment_record.amount),
        'domain_or_account': domain_name or account_name,
        'date_paid': payment_record.date_created.strftime(USER_DATE_FORMAT),
        'transaction_id': payment_record.public_transaction_id,
    }
    template_context.update(additional_context)

    return {
        'template_context': template_context,
        'email_to': email,
        'email_from': get_dimagi_from_email()
    }


def _user_active_in_domains(web_user, domain_name, account_name):
    if domain_name:
        return web_user and web_user.is_active_in_domain(domain_name)
    else:
        account = BillingAccount.objects.get(name=account_name)
        return any(web_user.is_active_in_domain(domain) for domain in account.get_domains())


def raise_except_and_log_accounting_comms_error(username):
    try:
        # needed for sentry
        raise AccountingCommunicationError()
    except AccountingCommunicationError:
        log_accounting_error(
            f"A payment attempt was made by a user that does not exist: {username}",
            show_stack_trace=True,
        )
