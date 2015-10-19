from django.test import TestCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.reminders.util import get_verified_number_for_recipient


class ReminderUtilTest(TestCase):
    def setUp(self):
        self.user = CommCareUser.create('test', 'test', 'test')

    def test_get_verified_number_for_recipient(self):
        self.assertIsNone(get_verified_number_for_recipient(self.user))

        self.user.phone_numbers = ['123', '456', '789']
        self.user.save_verified_number('test', '456', True)
        self.assertEqual(get_verified_number_for_recipient(self.user).phone_number, '456')

        self.user.save_verified_number('test', '789', True)
        self.assertEqual(get_verified_number_for_recipient(self.user).phone_number, '456')

        self.user.set_default_phone_number('789')
        self.assertEqual(self.user.phone_numbers, ['789', '123', '456'])
        v = get_verified_number_for_recipient(self.user)
        self.assertEqual(v.phone_number, '789')

        v.verified = False
        v.save()
        self.assertEqual(get_verified_number_for_recipient(self.user).phone_number, '456')

    def tearDown(self):
        self.user.delete()
