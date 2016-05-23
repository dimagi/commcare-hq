from django.test import TestCase

from casexml.apps.case.mock import CaseFactory
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

    def assert_restore(self, should_update=False):
        first_response = get_restore_response(self.domain, self.user, version='2.0')
        second_response = get_restore_response(self.domain, self.user, version='2.0')
        first_response = list(first_response.streaming_content)[0]
        second_response = list(second_response.streaming_content)[0]

        if should_update:
            self.assertNotEqual(first_response, second_response)
        else:
            self.assertEqual(first_response, second_response)

    def test_demo_restore_ON(self):
        self.assert_restore(should_update=True)

        turn_on_demo_mode(self.user, self.domain)
        self.assert_restore(should_update=False)

        turn_off_demo_mode(self.user)
        self.assert_restore(should_update=True)
