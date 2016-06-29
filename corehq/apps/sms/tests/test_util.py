#!/usr/bin/env python
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.util import (clean_phone_number,
    get_contact, ContactNotFoundException)
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.utils import is_commcarecase
from corehq.util.test_utils import create_test_case
from django.test import TestCase


class UtilTestCase(TestCase):
    
    def setUp(self):
        self.domain = 'test-domain'

    def testCleanPhoneNumber(self):
        phone_number = "  324 23-23421241"
        cleaned = clean_phone_number(phone_number)
        self.assertEquals(cleaned, "+3242323421241")

    def test_get_contact(self):
        with create_test_case(self.domain, 'contact', 'test-case') as case:
            user = CommCareUser.create(self.domain, 'test-user', '123')
            self.addCleanup(user.delete)

            contact = get_contact(self.domain, case.case_id)
            self.assertEqual(contact.case_id, case.case_id)
            self.assertTrue(is_commcarecase(contact))

            contact = get_contact(self.domain, user.get_id)
            self.assertEqual(contact.get_id, user.get_id)
            self.assertTrue(isinstance(contact, CommCareUser))

            with self.assertRaises(ContactNotFoundException):
                get_contact(self.domain, 'this-id-should-not-be-found')

            with self.assertRaises(ContactNotFoundException):
                get_contact(self.domain + 'x', case.case_id)

            with self.assertRaises(ContactNotFoundException):
                get_contact(self.domain + 'x', user.get_id)

    def test_apply_leniency(self):
        self.assertEqual('16175551234', apply_leniency(' 1 (617) 555-1234 '))
        self.assertEqual('16175551234', apply_leniency(' 1.617.555.1234 '))
        self.assertEqual('16175551234', apply_leniency(' +1 617 555 1234 '))
