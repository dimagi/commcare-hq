import uuid

from django.test import TestCase

from casexml.apps.case.models import CommCareCase

from corehq.apps.cloudcare.touchforms_api import (
    get_user_contributions_to_touchforms_session,
)
from corehq.apps.custom_data_fields.models import (
    PROFILE_SLUG,
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView


class SessionUtilsTest(TestCase):

    def tearDown(self):
        delete_all_users()
        super(SessionUtilsTest, self).tearDown()

    def test_load_session_data_for_mobile_worker(self):
        user = CommCareUser(
            domain='cloudcare-tests',
            username='worker@cloudcare-tests.commcarehq.org',
            _id=uuid.uuid4().hex
        )
        data = get_user_contributions_to_touchforms_session(user)
        self.assertEqual('worker', data['username'])
        self.assertEqual(user._id, data['user_id'])
        self.assertTrue(isinstance(data['user_data'], dict))

    def test_default_user_data(self):
        user = CommCareUser(
            domain='cloudcare-tests',
            username='worker@cloudcare-tests.commcarehq.org',
            _id=uuid.uuid4().hex
        )
        user_data = get_user_contributions_to_touchforms_session(user)['user_data']
        for key in ['commcare_first_name', 'commcare_last_name', 'commcare_phone_number']:
            self.assertEqual(None, user_data[key])
        user.first_name = 'first'
        user.last_name = 'last'
        user_data = get_user_contributions_to_touchforms_session(user)['user_data']
        self.assertEqual('first', user_data['commcare_first_name'])
        self.assertEqual('last', user_data['commcare_last_name'])

    def test_user_data_profile(self):
        definition = CustomDataFieldsDefinition(domain='cloudcare-tests', field_type=UserFieldsView.field_type)
        definition.save()
        definition.set_fields([
            Field(slug='word', label='A Word'),
        ])
        definition.save()
        profile = CustomDataFieldsProfile(name='prof', fields={'word': 'supernova'}, definition=definition)
        profile.save()
        user = CommCareUser.create(
            'cloudcare-tests',
            'worker@cloudcare-tests.commcarehq.org',
            'do you want to know a secret',
            None,
            None,
            uuid=uuid.uuid4().hex,
            metadata={PROFILE_SLUG: profile.id},
        )
        user_data = get_user_contributions_to_touchforms_session(user)['user_data']
        self.assertEqual(profile.id, user_data[PROFILE_SLUG])
        self.assertEqual('supernova', user_data['word'])
        definition.delete()

    def test_load_session_data_for_web_user(self):
        user = WebUser(
            username='web-user@example.com',
            _id=uuid.uuid4().hex
        )
        data = get_user_contributions_to_touchforms_session(user)
        self.assertEqual('web-user@example.com', data['username'])
        self.assertEqual(user._id, data['user_id'])
        self.assertTrue(isinstance(data['user_data'], dict))

    def test_load_session_data_for_commconnect_case(self):
        user = CommCareCase(
            name='A case',
            _id=uuid.uuid4().hex
        )
        data = get_user_contributions_to_touchforms_session(user)
        self.assertEqual('A case', data['username'])
        self.assertEqual(user._id, data['user_id'])
        self.assertEqual({}, data['user_data'])
