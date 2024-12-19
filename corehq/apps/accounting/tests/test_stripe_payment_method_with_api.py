from decimal import Decimal
from django.conf import settings
import stripe
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.models import StripePaymentMethod
from unittest import SkipTest
from unittest.mock import patch


class TestStripePaymentMethod(BaseAccountingTest):

    def setUp(self):
        super(TestStripePaymentMethod, self).setUp()
        # Dependabot-created PRs do not have access to secrets.
        # We skip test so the tests do not fail when dependabot creates new PR for dependency upgrades.
        # Or for developers running tests locally if they do not have stripe API key in their localsettings.
        if not settings.STRIPE_PRIVATE_KEY:
            raise SkipTest("Stripe API Key not set")
        stripe.api_key = settings.STRIPE_PRIVATE_KEY

        self.web_user_email = "test_web_user@gmail.com"
        self.dimagi_user_email = "test_dimagi_user@dimagi.com"
        self.billing_account = generator.billing_account(self.dimagi_user_email, self.web_user_email)

        self.stripe_customer = stripe.Customer.create(email=self.web_user_email)
        self.addCleanup(self.stripe_customer.delete)
        self.payment_method = StripePaymentMethod(web_user=self.web_user_email,
                                                  customer_id=self.stripe_customer.id)
        self.payment_method.save()
        # Stripe suggest using test tokens, see https://stripe.com/docs/testing.
        self.card = self.payment_method.create_card('tok_visa', self.billing_account, None)

        self.currency = generator.init_default_currency()

    def test_setup_autopay_for_first_time(self):
        self.assertEqual(self.billing_account.auto_pay_user, None)
        self.assertFalse(self.billing_account.auto_pay_enabled)

        self.payment_method.set_autopay(self.card, self.billing_account, None)
        refetched_card = self.payment_method.get_card(self.card.id)
        self.assertEqual(refetched_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'True'})
        self.assertEqual(self.billing_account.auto_pay_user, self.web_user_email)
        self.assertTrue(self.billing_account.auto_pay_enabled)

    def test_replace_card_for_autopay(self):
        self.payment_method.set_autopay(self.card, self.billing_account, None)
        refetched_card = self.payment_method.get_card(self.card.id)
        self.assertEqual(refetched_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'True'})
        self.assertEqual(self.billing_account.auto_pay_user, self.web_user_email)
        self.assertTrue(self.billing_account.auto_pay_enabled)

        # Replace autopay card
        other_web_user = "another_web_user@gmail.com"
        other_stripe_customer = stripe.Customer.create(email=other_web_user)
        self.addCleanup(other_stripe_customer.delete)
        other_payment_method = StripePaymentMethod(web_user=other_web_user, customer_id=other_stripe_customer.id)
        other_payment_method.save()
        other_stripe_card = other_payment_method.create_card('tok_mastercard', self.billing_account, None, True)

        self.assertEqual(self.billing_account.auto_pay_user, other_web_user)
        refetched_other_stripe_card = other_payment_method.get_card(other_stripe_card.id)
        self.assertTrue(refetched_other_stripe_card.metadata["auto_pay_{}".format(self.billing_account.id)])
        # The old autopay card should be removed from this billing account
        card = self.payment_method.all_cards[0]
        self.assertFalse(card.metadata["auto_pay_{}".format(self.billing_account.id)] == 'True')

    def test_same_card_used_by_multiple_billing_accounts(self):
        billing_account_2 = generator.billing_account(self.dimagi_user_email, self.web_user_email)

        # Use the card for first billing account
        self.payment_method.set_autopay(self.card, self.billing_account, None)
        refetched_card = self.payment_method.get_card(self.card.id)
        self.assertEqual(refetched_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'True'})
        self.assertEqual(self.billing_account.auto_pay_user, self.web_user_email)
        self.assertTrue(self.billing_account.auto_pay_enabled)

        # Use the same card for the second billing account
        self.payment_method.set_autopay(self.card, billing_account_2, None)
        refetched_card = self.payment_method.get_card(self.card.id)
        self.assertEqual(refetched_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'True',
                                            "auto_pay_{}".format(billing_account_2.id): 'True'})

    def test_unset_autopay(self):
        self.payment_method.set_autopay(self.card, self.billing_account, None)
        refetched_card = self.payment_method.get_card(self.card.id)
        self.assertEqual(refetched_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'True'})

        self.payment_method.unset_autopay(refetched_card, self.billing_account)
        refetched_card = self.payment_method.get_card(self.card.id)
        self.assertEqual(refetched_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'False'})
        self.assertIsNone(self.billing_account.auto_pay_user)
        self.assertFalse(self.billing_account.auto_pay_enabled)

    def test_get_stripe_customer_if_existed(self):
        customer = self.payment_method._get_or_create_stripe_customer()
        self.assertEqual(customer.id, self.stripe_customer.id)

    def test_create_stripe_customer_if_not_existed(self):
        web_user_email = generator.create_arbitrary_web_user_name()
        payment_method = StripePaymentMethod(web_user=web_user_email)
        customer = payment_method._get_or_create_stripe_customer()
        self.assertEqual(customer.email, web_user_email)
        self.addCleanup(customer.delete)

    def test_all_cards_raise_authentication_error_when_stripe_key_is_wrong(self):
        stripe.api_key = "12345678"
        with self.assertRaises(stripe.error.AuthenticationError):
            self.payment_method.all_cards

    def test_all_cards_return_the_correct_collection_of_cards_for_a_customer(self):
        # Get the payment methods that is associated with the customer
        payment_methods = stripe.PaymentMethod.list(
            customer=self.stripe_customer.id,
            type="card",
        )
        cards = self.payment_method.all_cards
        actual_card_ids = [card.fingerprint for card in cards]
        expected_card_ids = [payment_method.card.fingerprint for payment_method in payment_methods]
        self.assertCountEqual(actual_card_ids, expected_card_ids)

    def test_all_cards_return_empty_array_for_customer_have_no_cards(self):
        payment_method = StripePaymentMethod(web_user="no_card@gmail.com")
        self.addCleanup(payment_method.customer.delete)
        payment_method.save()
        cards = payment_method.all_cards
        self.assertEqual(len(cards), 0)

    def test_all_cards_return_empty_array_if_no_stripe_key(self):
        stripe.api_key = None
        with patch.object(settings, "STRIPE_PRIVATE_KEY", None):
            self.assertEqual(len(self.payment_method.all_cards), 0)

    def test_all_cards_serialized_return_the_correct_property_of_a_card(self):
        cards = self.payment_method.all_cards_serialized(self.billing_account)
        card = cards[0]
        self.assertEqual(card["brand"], "Visa")
        self.assertEqual(card["last4"], "4242")
        # stripe might change exp date for the test card, so we don't assert absolute value
        self.assertIn("exp_month", card)
        self.assertIn("exp_year", card)
        self.assertIn("token", card)
        self.assertFalse(card["is_autopay"])

    def test_get_card_return_the_correct_card_object(self):
        # TODO: Should I rename get_card parameter to card_id?
        card = self.payment_method.get_card(self.card.id)
        self.assertEqual(card.id, self.card.id)

    def test_get_autopay_card_when_no_autopay_card(self):
        self.assertEqual(self.billing_account.auto_pay_user, None)
        self.assertFalse(self.billing_account.auto_pay_enabled)
        result = self.payment_method.get_autopay_card(self.billing_account)
        self.assertIsNone(result)

    def test_get_autopay_card_when_only_one_autopay(self):
        self.payment_method.set_autopay(self.card, self.billing_account, None)
        result = self.payment_method.get_autopay_card(self.billing_account)
        self.assertEqual(result.id, self.card.id)

    def test_get_autopay_card_when_one_of_many_card_is_autopay(self):
        card2 = self.payment_method.create_card('tok_discover', self.billing_account, None, True)
        card3 = self.payment_method.create_card('tok_amex', self.billing_account, None, True)
        self.addCleanup(card2.delete)
        self.addCleanup(card3.delete)

        result = self.payment_method.get_autopay_card(self.billing_account)
        self.assertIsNotNone(result.id, card2.id)

        result = self.payment_method.get_autopay_card(self.billing_account)
        self.assertIsNotNone(result.id, card3.id)

    def test_remove_card_successful(self):
        self.assertEqual(len(self.payment_method.all_cards), 1)
        self.payment_method.set_autopay(self.card, self.billing_account, None)
        self.assertEqual(self.card.id, self.payment_method.get_autopay_card(self.billing_account).id)

        self.payment_method.remove_card(self.card.id)
        self.assertEqual(len(self.payment_method.all_cards), 0)
        self.billing_account.refresh_from_db()
        self.assertIsNone(self.billing_account.auto_pay_user)
        self.assertFalse(self.billing_account.auto_pay_enabled)

    def test_remove_card_non_existent(self):
        with self.assertRaises(stripe.error.InvalidRequestError):
            self.payment_method.remove_card("non_existent_card_id")

    def test_create_card_creates_card(self):
        created_card = self.payment_method.create_card('tok_discover', self.billing_account, None)
        self.addCleanup(created_card.delete)
        self.assertIsNotNone(created_card)
        self.assertEqual(created_card.brand, 'Discover')

    def test_create_charge_success(self):
        description = "Test charge"
        amount_in_dollars = Decimal('100')
        # Perform the charge
        transaction_id = self.payment_method.create_charge(
            card=self.card.id,
            amount_in_dollars=amount_in_dollars,
            description=description
        )
        # Verify the charge was successful by retrieving the charge from Stripe
        charge = stripe.Charge.retrieve(transaction_id)
        self.assertIsNotNone(charge)
        self.assertEqual(charge.amount, int(amount_in_dollars * Decimal('100')))
        self.assertEqual(charge.currency, self.currency.code.lower())
        self.assertEqual(charge.description, description)

    def test_create_charge_with_idempotency_key(self):
        description = "Test charge"
        amount_in_dollars = Decimal('100')
        # Idempotency key ensures that the charge can be retried without fear of double charging
        idempotency_key = f"{self.card.id}-idempotency-test"
        transaction_id_first_attempt = self.payment_method.create_charge(
            card=self.card.id,
            amount_in_dollars=amount_in_dollars,
            description=description,
            idempotency_key=idempotency_key
        )
        transaction_id_second_attempt = self.payment_method.create_charge(
            card=self.card.id,
            amount_in_dollars=amount_in_dollars,
            description=description,
            idempotency_key=idempotency_key
        )
        self.assertEqual(transaction_id_first_attempt, transaction_id_second_attempt)
