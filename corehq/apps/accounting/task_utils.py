from datetime import date

import settings
from corehq.apps.accounting.models import Invoice, StripePaymentMethod
from corehq.apps.accounting.utils import get_dimagi_from_email
from corehq.apps.users.models import WebUser
from corehq.util.view_utils import absolute_reverse


def get_context_to_send_autopay_failed_email(invoice_id):
    invoice = Invoice.objects.get(invoice_id)
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
