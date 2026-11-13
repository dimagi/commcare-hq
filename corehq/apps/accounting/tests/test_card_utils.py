from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import override_settings

from corehq.apps.accounting.models import PaymentMethodType, StripePaymentMethod
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.utils.cards import (
    get_autopay_card_and_owner_for_billing_account,
    get_payment_method_for_user,
    get_saved_cards_for_user,
    set_card_as_autopay_for_billing_account,
)


def mock_fake_card(card_id, *, metadata=None, brand='Visa', last4='4242', exp_month=1, exp_year=2030):
    return SimpleNamespace(
        id=card_id,
        metadata=metadata or {},
        brand=brand,
        last4=last4,
        exp_month=exp_month,
        exp_year=exp_year,
        object='card',
    )


class CardUtilsTest(BaseAccountingTest):
    def setUp(self):
        super().setUp()
        self.billing_contact = generator.create_arbitrary_web_user_name()
        self.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        self.currency = generator.init_default_currency()
        self.domain = generator.arbitrary_domain()
        self.billing_account = generator.billing_account(self.dimagi_user, self.billing_contact)
        self.billing_account.created_by_domain = self.domain.name
        self.billing_account.save()

    def test_get_autopay_card_and_owner_for_billing_account_no_autopay(self):
        card, owner = get_autopay_card_and_owner_for_billing_account(self.billing_account)
        assert card is None
        assert owner is None

    @patch('corehq.apps.accounting.models.StripePaymentMethod.objects.get')
    def test_get_autopay_card_and_owner_for_billing_account_with_autopay(self, get_mock):
        autopay_user = generator.arbitrary_user(domain_name=self.domain.name, is_active=True, is_webuser=True)
        self.billing_account.auto_pay_user = autopay_user.username
        self.billing_account.save()
        pm = Mock(spec=StripePaymentMethod)
        autopay_card = mock_fake_card('card_b')
        pm.get_autopay_card.return_value = autopay_card
        get_mock.return_value = pm

        card, owner = get_autopay_card_and_owner_for_billing_account(self.billing_account)

        assert card is autopay_card
        assert owner is autopay_user.username

    def test_card_as_autopay_for_billing_account_sets_autopay(self):
        pm = Mock(spec=StripePaymentMethod)
        card_obj = mock_fake_card('card_tok_123')
        pm.get_card.return_value = card_obj
        set_card_as_autopay_for_billing_account(pm, 'card_tok_123', self.billing_account, self.domain.name)

        pm.get_card.assert_called_once_with('card_tok_123')
        pm.set_autopay.assert_called_once_with(card_obj, self.billing_account, self.domain.name)

    def test_get_payment_method_for_user_always_returns(self):
        paying_user = generator.arbitrary_user(domain_name=self.domain.name, is_active=True, is_webuser=True)
        payment_method = get_payment_method_for_user(paying_user.username)
        assert payment_method.web_user == paying_user.username
        assert payment_method.method_type == PaymentMethodType.STRIPE

    @override_settings(STRIPE_PRIVATE_KEY=None)
    def test_get_saved_cards_for_user_no_stripe_key(self):
        paying_user = generator.arbitrary_user(domain_name=self.domain.name, is_active=True, is_webuser=True)
        cards = get_saved_cards_for_user(paying_user.username, self.billing_account)
        assert cards == []

    @override_settings(STRIPE_PRIVATE_KEY='something')
    @patch('corehq.apps.accounting.models.StripePaymentMethod.objects.get_or_create')
    def test_get_saved_cards_for_user_with_stripe_key(self, get_mock):
        paying_user = generator.arbitrary_user(domain_name=self.domain.name, is_active=True, is_webuser=True)
        pm = Mock(spec=StripePaymentMethod)
        pm.all_cards_serialized.return_value = [{'token': 'card_b'}]
        get_mock.return_value = (pm, False)
        cards = get_saved_cards_for_user(paying_user.username, self.billing_account)
        assert len(cards) == 1
        assert cards[0]['token'] == 'card_b'
