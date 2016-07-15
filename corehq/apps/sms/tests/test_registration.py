from corehq.apps.domain.calculations import num_mobile_users
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import incoming
from corehq.apps.sms.messages import (
    _MESSAGES,
    MSG_MOBILE_WORKER_INVITATION_START,
    MSG_MOBILE_WORKER_JAVA_INVITATION,
    MSG_MOBILE_WORKER_ANDROID_INVITATION,
    MSG_REGISTRATION_WELCOME_MOBILE_WORKER,
)
from corehq.apps.sms.models import (SQLMobileBackendMapping, SelfRegistrationInvitation,
    SMS, OUTGOING, PhoneNumber)
from corehq.apps.sms.resources.v0_5 import SelfRegistrationUserInfo
from corehq.apps.sms.tests.util import BaseSMSTest, delete_domain_phone_numbers
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from django.test import Client
from mock import patch


DUMMY_APP_ODK_URL = 'http://localhost/testapp'
DUMMY_REGISTRATION_URL = 'http://localhost/register'
DUMMY_APP_INFO_URL = 'http://localhost/appinfo'


class RegistrationTestCase(BaseSMSTest):

    def setUp(self):
        super(RegistrationTestCase, self).setUp()

        self.domain = 'sms-reg-test-domain'
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()

        self.create_account_and_subscription(self.domain)
        self.domain_obj = Domain.get(self.domain_obj.get_id)

        self.backend = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            is_global=False,
            domain=self.domain,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        SQLMobileBackendMapping.set_default_domain_backend(self.domain, self.backend)

        self.app_id = 'app_id'

    def tearDown(self):
        delete_domain_phone_numbers(self.domain)
        SelfRegistrationInvitation.objects.filter(domain=self.domain).delete()
        SQLMobileBackendMapping.unset_default_domain_backend(self.domain)
        self.backend.delete()
        self.domain_obj.delete()

        super(RegistrationTestCase, self).tearDown()

    def _get_last_sms(self, count=1, direction=None, phone_number=None):
        result = SMS.objects.filter(domain=self.domain)
        if direction:
            result = result.filter(direction=direction)

        if phone_number:
            result = result.filter(phone_number=phone_number)

        result = list(result[:count])
        self.assertEqual(len(result), count)
        return result

    def assertLastOutgoingSMS(self, phone_number, expected_texts):
        result = self._get_last_sms(
            count=len(expected_texts),
            direction=OUTGOING,
            phone_number=phone_number
        )
        actual_texts = set([sms.text for sms in result])
        self.assertEqual(actual_texts, set(expected_texts))

    def _get_sms_registration_invitation(self):
        # implicitly assert there is only one of these
        return SelfRegistrationInvitation.objects.get(domain=self.domain)

    def assertRegistrationInvitation(self, **kwargs):
        invite = self._get_sms_registration_invitation()

        for name, value in kwargs.items():
            self.assertEqual(getattr(invite, name), value)

    def test_sms_registration(self):
        formatted_username = format_username('tester', self.domain)

        # Test without mobile worker registration enabled
        incoming('+9991234567', 'JOIN {} WORKER tester'.format(self.domain), self.backend.hq_api_id)
        self.assertIsNone(CommCareUser.get_by_username(formatted_username))

        # Test with mobile worker registration enabled
        self.domain_obj.sms_mobile_worker_registration_enabled = True
        self.domain_obj.save()

        incoming('+9991234567', 'JOIN {} WORKER tester'.format(self.domain), self.backend.hq_api_id)
        self.assertIsNotNone(CommCareUser.get_by_username(formatted_username))

        # Test a duplicate registration
        prev_num_users = num_mobile_users(self.domain)
        incoming('+9991234568', 'JOIN {} WORKER tester'.format(self.domain), self.backend.hq_api_id)
        current_num_users = num_mobile_users(self.domain)
        self.assertEqual(prev_num_users, current_num_users)

    def test_other_registration_from_invite(self):
        self.domain_obj.sms_mobile_worker_registration_enabled = True
        self.domain_obj.enable_registration_welcome_sms_for_mobile_worker = True
        self.domain_obj.save()

        user_data = {'abc': 'def'}

        # Initiate Registration Workflow
        with patch.object(SelfRegistrationInvitation, 'get_app_odk_url', return_value=DUMMY_APP_ODK_URL):
            SelfRegistrationInvitation.initiate_workflow(
                self.domain,
                [SelfRegistrationUserInfo('999123', user_data)],
                app_id=self.app_id,
            )

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            odk_url=DUMMY_APP_ODK_URL,
            phone_type=None,
            android_only=False,
            require_email=False,
            custom_user_data=user_data,
            status=SelfRegistrationInvitation.STATUS_PENDING,
        )

        self.assertLastOutgoingSMS('+999123', [_MESSAGES[MSG_MOBILE_WORKER_INVITATION_START]])

        # Choose phone type 'other'
        incoming('+999123', '2', self.backend.hq_api_id)

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            odk_url=DUMMY_APP_ODK_URL,
            phone_type=SelfRegistrationInvitation.PHONE_TYPE_OTHER,
            android_only=False,
            require_email=False,
            custom_user_data=user_data,
            status=SelfRegistrationInvitation.STATUS_PENDING,
        )

        self.assertLastOutgoingSMS('+999123', [_MESSAGES[MSG_MOBILE_WORKER_JAVA_INVITATION].format(self.domain)])

        # Register over SMS
        incoming('+999123', 'JOIN {} WORKER test'.format(self.domain), self.backend.hq_api_id)
        user = CommCareUser.get_by_username(format_username('test', self.domain))
        self.assertIsNotNone(user)
        self.assertEqual(user.user_data, user_data)
        self.assertEqual(PhoneNumber.by_phone('999123').owner_id, user.get_id)

        self.assertLastOutgoingSMS('+999123', [_MESSAGES[MSG_REGISTRATION_WELCOME_MOBILE_WORKER]])

        self.assertRegistrationInvitation(
            status=SelfRegistrationInvitation.STATUS_REGISTERED,
        )

    def test_android_registration_from_invite(self):
        self.domain_obj.sms_mobile_worker_registration_enabled = True
        self.domain_obj.enable_registration_welcome_sms_for_mobile_worker = True
        self.domain_obj.save()

        user_data = {'abc': 'def'}

        # Initiate Registration Workflow
        with patch.object(SelfRegistrationInvitation, 'get_app_odk_url', return_value=DUMMY_APP_ODK_URL):
            SelfRegistrationInvitation.initiate_workflow(
                self.domain,
                [SelfRegistrationUserInfo('999123', user_data)],
                app_id=self.app_id,
            )

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            odk_url=DUMMY_APP_ODK_URL,
            phone_type=None,
            android_only=False,
            require_email=False,
            custom_user_data=user_data,
            status=SelfRegistrationInvitation.STATUS_PENDING,
        )

        self.assertLastOutgoingSMS('+999123', [_MESSAGES[MSG_MOBILE_WORKER_INVITATION_START]])

        # Choose phone type 'android'
        with patch.object(SelfRegistrationInvitation, 'get_user_registration_url', return_value=DUMMY_REGISTRATION_URL), \
                patch.object(SelfRegistrationInvitation, 'get_app_info_url', return_value=DUMMY_APP_INFO_URL):
            incoming('+999123', '1', self.backend.hq_api_id)

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            odk_url=DUMMY_APP_ODK_URL,
            phone_type=SelfRegistrationInvitation.PHONE_TYPE_ANDROID,
            android_only=False,
            require_email=False,
            custom_user_data=user_data,
            status=SelfRegistrationInvitation.STATUS_PENDING,
        )

        self.assertLastOutgoingSMS('+999123', [
            _MESSAGES[MSG_MOBILE_WORKER_ANDROID_INVITATION].format(DUMMY_REGISTRATION_URL),
            '[commcare app - do not delete] {}'.format(DUMMY_APP_INFO_URL),
        ])

        invite = self._get_sms_registration_invitation()
        c = Client()
        response = c.post('/a/{}/settings/users/commcare/register/{}/'.format(self.domain, invite.token), {
            'username': 'new_user',
            'password': 'abc',
            'password2': 'abc',
            'email': 'new_user@dimagi.com',
        })
        self.assertEqual(response.status_code, 200)

        user = CommCareUser.get_by_username(format_username('new_user', self.domain))
        self.assertIsNotNone(user)
        self.assertEqual(user.user_data, user_data)
        self.assertEqual(user.email, 'new_user@dimagi.com')
        self.assertEqual(PhoneNumber.by_phone('999123').owner_id, user.get_id)

        self.assertRegistrationInvitation(
            status=SelfRegistrationInvitation.STATUS_REGISTERED,
        )

    def test_android_only_registration_from_invite(self):
        self.domain_obj.sms_mobile_worker_registration_enabled = True
        self.domain_obj.enable_registration_welcome_sms_for_mobile_worker = True
        self.domain_obj.save()

        # Initiate Registration Workflow
        with patch.object(SelfRegistrationInvitation, 'get_app_odk_url', return_value=DUMMY_APP_ODK_URL), \
                patch.object(SelfRegistrationInvitation, 'get_user_registration_url', return_value=DUMMY_REGISTRATION_URL), \
                patch.object(SelfRegistrationInvitation, 'get_app_info_url', return_value=DUMMY_APP_INFO_URL):
            SelfRegistrationInvitation.initiate_workflow(
                self.domain,
                [SelfRegistrationUserInfo('999123')],
                app_id=self.app_id,
                android_only=True,
            )

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            odk_url=DUMMY_APP_ODK_URL,
            phone_type=SelfRegistrationInvitation.PHONE_TYPE_ANDROID,
            android_only=True,
            require_email=False,
            custom_user_data={},
            status=SelfRegistrationInvitation.STATUS_PENDING,
        )

        self.assertLastOutgoingSMS('+999123', [
            _MESSAGES[MSG_MOBILE_WORKER_ANDROID_INVITATION].format(DUMMY_REGISTRATION_URL),
            '[commcare app - do not delete] {}'.format(DUMMY_APP_INFO_URL),
        ])

        invite = self._get_sms_registration_invitation()
        c = Client()
        response = c.post('/a/{}/settings/users/commcare/register/{}/'.format(self.domain, invite.token), {
            'username': 'new_user',
            'password': 'abc',
            'password2': 'abc',
            'email': 'new_user@dimagi.com',
        })
        self.assertEqual(response.status_code, 200)

        user = CommCareUser.get_by_username(format_username('new_user', self.domain))
        self.assertIsNotNone(user)
        self.assertEqual(user.user_data, {})
        self.assertEqual(user.email, 'new_user@dimagi.com')
        self.assertEqual(PhoneNumber.by_phone('999123').owner_id, user.get_id)

        self.assertRegistrationInvitation(
            status=SelfRegistrationInvitation.STATUS_REGISTERED,
        )

    def test_custom_message_for_normal_workflow(self):
        self.domain_obj.sms_mobile_worker_registration_enabled = True
        self.domain_obj.enable_registration_welcome_sms_for_mobile_worker = True
        self.domain_obj.save()

        # Initiate Registration Workflow
        with patch.object(SelfRegistrationInvitation, 'get_app_odk_url', return_value=DUMMY_APP_ODK_URL):
            SelfRegistrationInvitation.initiate_workflow(
                self.domain,
                [SelfRegistrationUserInfo('999123')],
                app_id=self.app_id,
                custom_first_message='Custom Message',
            )

        self.assertLastOutgoingSMS('+999123', ['Custom Message'])

    def test_custom_message_for_android_only_workflow(self):
        self.domain_obj.sms_mobile_worker_registration_enabled = True
        self.domain_obj.enable_registration_welcome_sms_for_mobile_worker = True
        self.domain_obj.save()

        # Initiate Registration Workflow
        with patch.object(SelfRegistrationInvitation, 'get_app_odk_url', return_value=DUMMY_APP_ODK_URL), \
                patch.object(SelfRegistrationInvitation, 'get_user_registration_url', return_value=DUMMY_REGISTRATION_URL), \
                patch.object(SelfRegistrationInvitation, 'get_app_info_url', return_value=DUMMY_APP_INFO_URL):
            SelfRegistrationInvitation.initiate_workflow(
                self.domain,
                [SelfRegistrationUserInfo('999123')],
                app_id=self.app_id,
                android_only=True,
                custom_first_message='Sign up here: {}',
            )

        self.assertLastOutgoingSMS('+999123', [
            'Sign up here: {}'.format(DUMMY_REGISTRATION_URL),
            '[commcare app - do not delete] {}'.format(DUMMY_APP_INFO_URL),
        ])
