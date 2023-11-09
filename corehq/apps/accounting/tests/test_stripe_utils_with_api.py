from django.test import TestCase
import stripe
from corehq.apps.accounting.models import StripePaymentMethod
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.utils.stripe import get_customer_cards, charge_through_stripe


class StripeUtilsTests(TestCase):

    def setUp(self):
        super().setUp()
        self.web_user_email = "test@example.com"

        # Set up Stripe customer with a card
        self.stripe_customer = stripe.Customer.create(email=self.web_user_email)
        self.addCleanup(self.stripe_customer.delete)

        # Create a corresponding local StripePaymentMethod instance
        self.dimagi_user_email = "test_dimagi_user@dimagi.com"
        self.billing_account = generator.billing_account(self.dimagi_user_email, self.web_user_email)
        self.addCleanup(self.billing_account.delete)
        self.payment_method = StripePaymentMethod.objects.create(
            web_user=self.web_user_email,
            customer_id=self.stripe_customer.id
        )
        self.payment_method.save()
        self.card = self.payment_method.create_card('tok_visa', self.billing_account, None)
        self.payment_method.create_card('tok_discover', self.billing_account, None)

    def test_get_customer_cards(self):
        cards = get_customer_cards(self.web_user_email)
        self.assertIsNotNone(cards)
        self.assertEqual(len(cards['data']), 2)
        self.assertEqual(cards['data'][0]['last4'], '4242')
        self.assertEqual(cards['data'][0]['brand'], 'Visa')
        self.assertEqual(cards['data'][0].id, self.card.id)

    def test_charge_through_stripe_successful(self):
        amount_in_dollars = 10
        currency = 'usd'
        description = 'Test charge'
        charge = charge_through_stripe(
            card=self.card.id,
            customer=self.stripe_customer.id,
            amount_in_dollars=amount_in_dollars,
            currency=currency,
            description=description
        )
        self.assertIsNotNone(charge)
        self.assertEqual(charge.amount, amount_in_dollars * 100)  # Stripe uses cents
        self.assertEqual(charge.currency, currency)
        self.assertEqual(charge.description, description)
