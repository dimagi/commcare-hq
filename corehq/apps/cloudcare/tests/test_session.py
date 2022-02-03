import uuid

from django.test import TestCase

from corehq.apps.cloudcare.touchforms_api import (
    get_user_contributions_to_touchforms_session,
)
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
    PROFILE_SLUG,
)
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.models import CommCareCase


class SessionUtilsTest(TestCase):

    def test_load_session_data_for_mobile_worker(self):
        user = CommCareUser(
            domain='cloudcare-tests',
            username='worker@cloudcare-tests.commcarehq.org',
            _id=uuid.uuid4().hex
        )
        data = get_user_contributions_to_touchforms_session('cloudcare-tests', user)
        self.assertEqual('worker', data['username'])
        self.assertEqual(user._id, data['user_id'])
        self.assertTrue(isinstance(data['user_data'], dict))
        self.assertTrue(data['user_data']['commcare_project'], 'cloudcare-tests')

    def test_default_user_data(self):
        user = CommCareUser(
            domain='cloudcare-tests',
            username='worker@cloudcare-tests.commcarehq.org',
            _id=uuid.uuid4().hex
        )
        user_data = get_user_contributions_to_touchforms_session('cloudcare-tests', user)['user_data']
        for key in ['commcare_first_name', 'commcare_last_name', 'commcare_phone_number']:
            self.assertEqual(None, user_data[key])
        user.first_name = 'first'
        user.last_name = 'last'
        user_data = get_user_contributions_to_touchforms_session('cloudcare-tests', user)['user_data']
        self.assertEqual('first', user_data['commcare_first_name'])
        self.assertEqual('last', user_data['commcare_last_name'])

    def test_user_data_profile(self):
        definition = CustomDataFieldsDefinition(domain='cloudcare-tests', field_type=UserFieldsView.field_type)
        definition.save()
        definition.set_fields([
            Field(slug='word', label='A Word'),
        ])
        definition.save()
        self.addCleanup(definition.delete)
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
        self.addCleanup(user.delete, None, None)
        user_data = get_user_contributions_to_touchforms_session('cloudcare-tests', user)['user_data']
        self.assertEqual(profile.id, user_data[PROFILE_SLUG])
        self.assertEqual('supernova', user_data['word'])

    def test_load_session_data_for_web_user(self):
        user = WebUser(
            username='web-user@example.com',
            _id=uuid.uuid4().hex
        )
        data = get_user_contributions_to_touchforms_session('cloudcare-tests', user)
        self.assertEqual('web-user@example.com', data['username'])
        self.assertEqual(user._id, data['user_id'])
        self.assertTrue(isinstance(data['user_data'], dict))
        self.assertTrue(data['user_data']['commcare_project'], 'cloudcare-tests')

    def test_load_session_data_for_commconnect_case(self):
        user = CommCareCase(
            name='A case',
            case_id=uuid.uuid4().hex
        )
        data = get_user_contributions_to_touchforms_session('cloudcare-tests', user)
        self.assertEqual('A case', data['username'])
        self.assertEqual(user.case_id, data['user_id'])
        self.assertEqual({}, data['user_data'])
