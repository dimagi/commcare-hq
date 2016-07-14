from corehq.apps.domain.calculations import num_mobile_users
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import incoming
from corehq.apps.sms.messages import (
    _MESSAGES,
    MSG_MOBILE_WORKER_INVITATION_START,
    MSG_MOBILE_WORKER_JAVA_INVITATION,
    MSG_REGISTRATION_WELCOME_MOBILE_WORKER,
)
from corehq.apps.sms.models import SQLMobileBackendMapping, SelfRegistrationInvitation, SMS, OUTGOING
from corehq.apps.sms.resources.v0_5 import SelfRegistrationUserInfo
from corehq.apps.sms.tests.util import BaseSMSTest, delete_domain_phone_numbers
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from mock import patch


def get_app_odk_url():
    return 'http://localhost/testapp'


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

    def _get_last_sms(self):
        result = SMS.objects.filter(domain=self.domain).order_by('-date')[:1]
        return result[0] if len(result) > 0 else None

    def assertLastOutgoingSMS(self, phone_number, text):
        sms = self._get_last_sms()
        self.assertEqual(sms.direction, OUTGOING)
        self.assertEqual(sms.phone_number, phone_number)
        self.assertEqual(sms.text, text)

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
        with patch.object(SelfRegistrationInvitation, 'get_app_odk_url', return_value=get_app_odk_url()):
            SelfRegistrationInvitation.initiate_workflow(
                self.domain,
                [SelfRegistrationUserInfo('999123', user_data)],
                app_id=self.app_id,
            )

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            odk_url=get_app_odk_url(),
            phone_type=None,
            android_only=False,
            require_email=False,
            custom_user_data=user_data,
        )

        self.assertLastOutgoingSMS('+999123', _MESSAGES[MSG_MOBILE_WORKER_INVITATION_START])

        # Choose phone type 'other'
        incoming('+999123', '2', self.backend.hq_api_id)

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            odk_url=get_app_odk_url(),
            phone_type=SelfRegistrationInvitation.PHONE_TYPE_OTHER,
            android_only=False,
            require_email=False,
            custom_user_data=user_data,
        )

        self.assertLastOutgoingSMS('+999123', _MESSAGES[MSG_MOBILE_WORKER_JAVA_INVITATION].format(self.domain))

        # Register over SMS
        incoming('+999123', 'JOIN {} WORKER test'.format(self.domain), self.backend.hq_api_id)
        user = CommCareUser.get_by_username(format_username('test', self.domain))
        self.assertIsNotNone(user)
        self.assertEqual(user.user_data, user_data)

        self.assertLastOutgoingSMS('+999123', _MESSAGES[MSG_REGISTRATION_WELCOME_MOBILE_WORKER])
