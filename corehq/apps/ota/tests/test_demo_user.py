from django.test import TestCase

from casexml.apps.case.mock import CaseFactory
from corehq.apps.custom_data_fields.models import (
    COMMCARE_USER_TYPE_KEY,
    COMMCARE_USER_TYPE_DEMO
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.ota.views import get_restore_response
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.ota.utils import turn_on_demo_mode, turn_off_demo_mode


class TestDemoUser(TestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_users()
        cls.domain = 'main-domain'
        cls.project = create_domain(cls.domain)
        cls.user = CommCareUser.create(cls.domain, 'test@main-domain.commcarehq.org', 'secret')
        factory = CaseFactory()
        factory.create_case(owner_id=cls.user._id, update={'custom_prop': 'custom_value'})

    def _raw_restore_response(self):
        streaming_response = get_restore_response(self.domain, self.user, version='2.0')
        return list(streaming_response.streaming_content)[0]

    def _assert_restore(self, should_change=True):
        # makes two consective restore requests and compares them
        first_response = self._raw_restore_response()
        second_response = self._raw_restore_response()

        if should_change:
            # sync-log id should keep changing between subsequent restores
            self.assertNotEqual(first_response, second_response)
        else:
            # restore should be cached, and sync-log id shouldn't change
            self.assertEqual(first_response, second_response)

    def test_demo_restore(self):
        # restore should always update for normal users
        self._assert_restore(should_change=True)

        # restore should be frozen for demo user
        turn_on_demo_mode(self.user, self.domain)
        self._assert_restore(should_change=False)

        # restore should update once demo mode is off
        turn_off_demo_mode(self.user)
        self._assert_restore(should_change=True)

    def test_demo_user_data_in_restore(self):
        # assert that demo users have '<data user_type="demo">' element in restore XML
        demo_element = '<data key="{}">{}</data>'.format(COMMCARE_USER_TYPE_KEY, COMMCARE_USER_TYPE_DEMO)

        turn_off_demo_mode(self.user)
        restore = self._raw_restore_response()
        self.assertFalse(demo_element in restore)

        turn_on_demo_mode(self.user, self.domain)
        restore = self._raw_restore_response()
        self.assertTrue(demo_element in restore)
