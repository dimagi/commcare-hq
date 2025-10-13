from django.conf import settings

from corehq.apps.accounting.models import PaymentMethodType, StripePaymentMethod


def get_autopay_card_and_owner_for_billing_account(account):
    if not account.auto_pay_enabled:
        return None, None

    auto_payer = account.auto_pay_user
    payment_method = StripePaymentMethod.objects.get(web_user=auto_payer)

    # makes API call to Stripe. Returns a stripe.Card object
    autopay_card = payment_method.get_autopay_card(account)
    return autopay_card, auto_payer


def set_card_as_autopay_for_billing_account(payment_method, card_token, account, domain):
    card = payment_method.get_card(card_token)
    payment_method.set_autopay(card, account, domain)


def get_payment_method_for_user(username):
    payment_method, _ = StripePaymentMethod.objects.get_or_create(
        web_user=username,
        method_type=PaymentMethodType.STRIPE,
    )
    return payment_method


def get_saved_cards_for_user(username, account):
    if not settings.STRIPE_PRIVATE_KEY:
        return []

    payment_method = get_payment_method_for_user(username)
    return payment_method.all_cards_serialized(account)
