from stripe import Card

from corehq.apps.accounting.models import BillingAccount, StripePaymentMethod


def get_autopay_card_and_owner_for_billing_account(account: BillingAccount) -> tuple[None | Card, None | str]:
    if not account.auto_pay_enabled:
        return None, None

    auto_payer = account.auto_pay_user
    payment_method = StripePaymentMethod.objects.get(web_user=auto_payer)

    # makes API call to Stripe:
    autopay_card = payment_method.get_autopay_card(account)
    return autopay_card, auto_payer
