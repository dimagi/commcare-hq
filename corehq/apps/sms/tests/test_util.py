#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.util import (clean_phone_number,
    get_contact, ContactNotFoundException)
from corehq.apps.users.models import CommCareUser
from django.test import TestCase


class UtilTestCase(TestCase):
    
    def setUp(self):
        self.case = CommCareCase(domain='test-domain', name='test-case')
        self.case.save()
        self.user = CommCareUser.create('test-domain', 'test-user', '123')

    def tearDown(self):
        self.case.delete()
        self.user.delete()

    def testCleanPhoneNumber(self):
        phone_number = "  324 23-23421241"
        cleaned = clean_phone_number(phone_number)
        self.assertEquals(cleaned, "+3242323421241")

    def test_get_contact(self):
        contact = get_contact(self.case.get_id)
        self.assertEqual(contact.get_id, self.case.get_id)
        self.assertTrue(isinstance(contact, CommCareCase))

        contact = get_contact(self.user.get_id)
        self.assertEqual(contact.get_id, self.user.get_id)
        self.assertTrue(isinstance(contact, CommCareUser))

        with self.assertRaises(ContactNotFoundException):
            get_contact('this-id-should-not-be-found')

    def test_apply_leniency(self):
        self.assertEqual('16175551234', apply_leniency(' 1 (617) 555-1234 '))
        self.assertEqual('16175551234', apply_leniency(' 1.617.555.1234 '))
        self.assertEqual('16175551234', apply_leniency(' +1 617 555 1234 '))
