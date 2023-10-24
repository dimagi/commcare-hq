from django.conf import settings
from corehq.apps.accounting.utils import log_accounting_info


def get_customer_cards(username, domain):
    from corehq.apps.accounting.models import (
        StripePaymentMethod, PaymentMethodType,
    )
    import stripe
    try:
        payment_method = StripePaymentMethod.objects.get(
            web_user=username,
            method_type=PaymentMethodType.STRIPE
        )
        stripe_customer = payment_method.customer
        return dict(stripe_customer.cards)
    except StripePaymentMethod.DoesNotExist:
        pass
    except stripe.error.AuthenticationError:
        if not settings.STRIPE_PRIVATE_KEY:
            log_accounting_info("Private key is not defined in settings")
        else:
            raise
    return None
