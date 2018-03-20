from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.reminders.util import get_two_way_number_for_recipient
from corehq.apps.sms.tests.util import delete_domain_phone_numbers


class ReminderUtilTest(TestCase):

    def setUp(self):
        self.user = CommCareUser.create('test', 'test', 'test')

    def test_get_two_way_number_for_recipient(self):
        self.assertIsNone(get_two_way_number_for_recipient(self.user))

        self.user.phone_numbers = ['123', '456', '789']
        entry = self.user.get_or_create_phone_entry('456')
        entry.set_two_way()
        entry.set_verified()
        entry.save()
        self.assertEqual(get_two_way_number_for_recipient(self.user).phone_number, '456')

        entry = self.user.get_or_create_phone_entry('789')
        entry.set_two_way()
        entry.set_verified()
        entry.save()
        self.assertEqual(get_two_way_number_for_recipient(self.user).phone_number, '456')

        self.user.set_default_phone_number('789')
        self.assertEqual(self.user.phone_numbers, ['789', '123', '456'])
        v = get_two_way_number_for_recipient(self.user)
        self.assertEqual(v.phone_number, '789')

        v.verified = False
        v.is_two_way = False
        v.pending_verification = False
        v.save()
        self.assertEqual(get_two_way_number_for_recipient(self.user).phone_number, '456')

    def tearDown(self):
        delete_domain_phone_numbers('test')
        self.user.delete()
