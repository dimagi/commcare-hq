#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.hqcase.utils import update_case
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.util import (clean_phone_number,
    get_contact, ContactNotFoundException, is_contact_active)
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import is_commcarecase
from corehq.util.test_utils import create_test_case
from django.test import TestCase


class UtilTestCase(TestCase):
    
    def setUp(self):
        self.domain = 'test-domain'
        self.user = CommCareUser.create(self.domain, 'test-user', '123')

    def tearDown(self):
        self.user.delete()

    def testCleanPhoneNumber(self):
        phone_number = "  324 23-23421241"
        cleaned = clean_phone_number(phone_number)
        self.assertEquals(cleaned, "+3242323421241")

    @run_with_all_backends
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

    @run_with_all_backends
    def test_is_contact_active_for_case(self):
        with create_test_case(self.domain, 'contact', 'test-case') as case:
            self.assertTrue(is_contact_active(self.domain, 'CommCareCase', case.case_id))
            update_case(self.domain, case.case_id, close=True)
            self.assertFalse(is_contact_active(self.domain, 'CommCareCase', case.case_id))

    def test_is_contact_active_for_user(self):
        self.assertTrue(is_contact_active(self.domain, 'CommCareUser', self.user.get_id))

        self.user.is_active = False
        self.user.save()
        self.assertFalse(is_contact_active(self.domain, 'CommCareUser', self.user.get_id))

        self.user.is_active = True
        self.user.save()
        self.assertTrue(is_contact_active(self.domain, 'CommCareUser', self.user.get_id))

    def test_apply_leniency(self):
        self.assertEqual('16175551234', apply_leniency(' 1 (617) 555-1234 '))
        self.assertEqual('16175551234', apply_leniency(' 1.617.555.1234 '))
        self.assertEqual('16175551234', apply_leniency(' +1 617 555 1234 '))
