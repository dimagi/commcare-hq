#!/usr/bin/env python
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

import pytest
from unmagic import fixture, use

from corehq.apps.accounting.models import (
    BillingAccount,
    CreditAdjustmentReason,
    CreditLine,
    StripePaymentMethod,
)
from corehq.apps.hqcase.utils import update_case
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.util import (
    ContactNotFoundException,
    can_self_enable_messaging,
    clean_phone_number,
    get_contact,
    is_contact_active,
    is_superuser_or_contractor,
)
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.tasks import sync_case_for_messaging
from corehq.util.test_utils import create_test_case, flag_enabled


class UtilTestCase(TestCase):

    def setUp(self):
        self.domain = 'test-domain'
        self.user = CommCareUser.create(self.domain, 'test-user', '123', None, None)

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)

    def testCleanPhoneNumber(self):
        phone_number = "  324 23-23421241"
        cleaned = clean_phone_number(phone_number)
        self.assertEqual(cleaned, "+3242323421241")

    def test_get_contact_for_case(self):
        with create_test_case(self.domain, 'contact', 'test-case') as case:
            contact = get_contact(self.domain, case.case_id)
            self.assertEqual(contact.case_id, case.case_id)
            self.assertTrue(is_commcarecase(contact))

            with self.assertRaises(ContactNotFoundException):
                get_contact(self.domain + 'x', case.case_id)

    def test_get_contact_for_user(self):
        contact = get_contact(self.domain, self.user.get_id)
        self.assertEqual(contact.get_id, self.user.get_id)
        self.assertTrue(isinstance(contact, CommCareUser))

        with self.assertRaises(ContactNotFoundException):
            get_contact(self.domain + 'x', self.user.get_id)

    def test_contact_not_found(self):
        with self.assertRaises(ContactNotFoundException):
            get_contact(self.domain, 'this-id-should-not-be-found')

    def test_is_contact_active_for_case(self):
        with create_test_case(self.domain, 'contact', 'test-case') as case:
            self.assertTrue(is_contact_active(self.domain, 'CommCareCase', case.case_id))
            update_case(self.domain, case.case_id, close=True)
            sync_case_for_messaging(self.domain, case.case_id)
            self.assertFalse(is_contact_active(self.domain, 'CommCareCase', case.case_id))

    def test_is_contact_active_for_user(self):
        self.assertTrue(is_contact_active(self.domain, 'CommCareUser', self.user.get_id))

        self.user.set_is_active(self.domain, False)
        self.user.save()
        self.assertFalse(is_contact_active(self.domain, 'CommCareUser', self.user.get_id))

        self.user.set_is_active(self.domain, True)
        self.user.save()
        self.assertTrue(is_contact_active(self.domain, 'CommCareUser', self.user.get_id))

    def test_apply_leniency(self):
        self.assertEqual('16175551234', apply_leniency(' 1 (617) 555-1234 '))
        self.assertEqual('16175551234', apply_leniency(' 1.617.555.1234 '))
        self.assertEqual('16175551234', apply_leniency(' +1 617 555 1234 '))


def test_contractor():
    user = CouchUser(username="eric")
    with flag_enabled('IS_CONTRACTOR'):
        assert is_superuser_or_contractor(user)


def test_superuser():
    user = CouchUser(username="john", is_superuser=True)
    assert is_superuser_or_contractor(user)


def test_normal_user():
    user = CouchUser(username="michael")
    assert not is_superuser_or_contractor(user)


@use('db')
@fixture
def billing_account():
    account, __ = BillingAccount.get_or_create_account_by_domain(
        'test-domain', created_by='admin@example.com'
    )
    yield account


@use(billing_account)
class TestCanSelfEnableMessaging:
    couch_user = CouchUser(username='clifford')

    def test_autopay(self):
        account = billing_account()
        account.auto_pay_user = 'admin@example.com'
        account.save()
        assert can_self_enable_messaging('test-domain', self.couch_user)

    @pytest.mark.parametrize('amounts, expected', [
        ([Decimal('99.99')], False),
        ([Decimal('100')], True),
        ([Decimal('60'), Decimal('40')], True),
    ])
    def test_payments(self, amounts, expected):
        for amount in amounts:
            CreditLine.add_credit(amount, account=billing_account())

        assert can_self_enable_messaging('test-domain', self.couch_user) is expected

    def test_spent_payments_count(self):
        account = billing_account()
        CreditLine.add_credit(Decimal('100'), account=account)
        CreditLine.add_credit(Decimal('-100'), account=account)
        assert can_self_enable_messaging('test-domain', self.couch_user)

    def test_transfers_dont_count(self):
        account = billing_account()
        CreditLine.add_credit(
            Decimal('100'),
            account=account,
            reason=CreditAdjustmentReason.TRANSFER,
        )
        assert not can_self_enable_messaging('test-domain', self.couch_user)

    @pytest.mark.parametrize('cards, expected', [
        (['card'], True),
        ([], False),
    ])
    def test_saved_card(self, cards, expected):
        StripePaymentMethod.objects.create(web_user=self.couch_user.username)
        with patch.object(StripePaymentMethod, 'all_cards', cards):
            assert can_self_enable_messaging('test-domain', self.couch_user) is expected
