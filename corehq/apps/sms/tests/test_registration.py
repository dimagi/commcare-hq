import base64
import json
from corehq.apps.accounting.models import (BillingAccount, DefaultProductPlan,
    SoftwarePlanEdition, SubscriptionAdjustment, Subscription)
from corehq.apps.accounting.tests import generator
from corehq.apps.domain.calculations import num_mobile_users
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import incoming
from corehq.apps.sms.messages import (
    _MESSAGES,
    MSG_MOBILE_WORKER_INVITATION_START,
    MSG_MOBILE_WORKER_JAVA_INVITATION,
    MSG_MOBILE_WORKER_ANDROID_INVITATION,
    MSG_REGISTRATION_WELCOME_MOBILE_WORKER,
    MSG_REGISTRATION_INSTALL_COMMCARE,
)
from corehq.apps.sms.models import (SQLMobileBackendMapping, SelfRegistrationInvitation,
    SMS, OUTGOING, PhoneNumber)
from corehq.apps.sms.resources.v0_5 import SelfRegistrationUserInfo
from corehq.apps.sms.tests.util import BaseSMSTest, delete_domain_phone_numbers
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.util import format_username
from corehq.const import GOOGLE_PLAY_STORE_COMMCARE_URL
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from django_prbac.models import Role
from django.test import Client, TestCase
from mock import patch, Mock


DUMMY_APP_ODK_URL = 'http://localhost/testapp'
DUMMY_REGISTRATION_URL = 'http://localhost/register'
DUMMY_APP_INFO_URL = 'http://localhost/appinfo'
DUMMY_APP_INFO_URL_B64 = base64.b64encode(DUMMY_APP_INFO_URL)


def noop(*args, **kwargs):
    pass


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

        self.default_user_data = {'commcare_project': self.domain}

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

        result = result.order_by('-date')
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
        SelfRegistrationInvitation.initiate_workflow(
            self.domain,
            [SelfRegistrationUserInfo('999123', user_data)],
            app_id=self.app_id,
        )

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
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
        self.assertEqual(user.user_data, dict(self.default_user_data, **user_data))
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
        SelfRegistrationInvitation.initiate_workflow(
            self.domain,
            [SelfRegistrationUserInfo('999123', user_data)],
            app_id=self.app_id,
        )

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            phone_type=None,
            android_only=False,
            require_email=False,
            custom_user_data=user_data,
            status=SelfRegistrationInvitation.STATUS_PENDING,
        )

        self.assertLastOutgoingSMS('+999123', [_MESSAGES[MSG_MOBILE_WORKER_INVITATION_START]])

        # Choose phone type 'android'
        with patch('corehq.apps.sms.models.SelfRegistrationInvitation.odk_url') as mock_odk_url, \
                patch.object(SelfRegistrationInvitation, 'get_user_registration_url', return_value=DUMMY_REGISTRATION_URL), \
                patch.object(SelfRegistrationInvitation, 'get_app_info_url', return_value=DUMMY_APP_INFO_URL):
            mock_odk_url.__get__ = Mock(return_value=DUMMY_APP_ODK_URL)
            incoming('+999123', '1', self.backend.hq_api_id)

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            phone_type=SelfRegistrationInvitation.PHONE_TYPE_ANDROID,
            android_only=False,
            require_email=False,
            custom_user_data=user_data,
            status=SelfRegistrationInvitation.STATUS_PENDING,
        )

        self.assertLastOutgoingSMS('+999123', [
            _MESSAGES[MSG_MOBILE_WORKER_ANDROID_INVITATION].format(DUMMY_REGISTRATION_URL),
            '[commcare app - do not delete] {}'.format(DUMMY_APP_INFO_URL_B64),
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
        self.assertEqual(user.user_data, dict(self.default_user_data, **user_data))
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
        with patch('corehq.apps.sms.models.SelfRegistrationInvitation.odk_url') as mock_odk_url, \
                patch.object(SelfRegistrationInvitation, 'get_user_registration_url', return_value=DUMMY_REGISTRATION_URL), \
                patch.object(SelfRegistrationInvitation, 'get_app_info_url', return_value=DUMMY_APP_INFO_URL):
            mock_odk_url.__get__ = Mock(return_value=DUMMY_APP_ODK_URL)
            SelfRegistrationInvitation.initiate_workflow(
                self.domain,
                [SelfRegistrationUserInfo('999123')],
                app_id=self.app_id,
                android_only=True,
            )

        self.assertRegistrationInvitation(
            phone_number='999123',
            app_id=self.app_id,
            phone_type=SelfRegistrationInvitation.PHONE_TYPE_ANDROID,
            android_only=True,
            require_email=False,
            custom_user_data={},
            status=SelfRegistrationInvitation.STATUS_PENDING,
        )

        self.assertLastOutgoingSMS('+999123', [
            _MESSAGES[MSG_MOBILE_WORKER_ANDROID_INVITATION].format(DUMMY_REGISTRATION_URL),
            '[commcare app - do not delete] {}'.format(DUMMY_APP_INFO_URL_B64),
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
        self.assertEqual(user.user_data, self.default_user_data)
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
        with patch('corehq.apps.sms.models.SelfRegistrationInvitation.odk_url') as mock_odk_url, \
                patch.object(SelfRegistrationInvitation, 'get_user_registration_url', return_value=DUMMY_REGISTRATION_URL), \
                patch.object(SelfRegistrationInvitation, 'get_app_info_url', return_value=DUMMY_APP_INFO_URL):
            mock_odk_url.__get__ = Mock(return_value=DUMMY_APP_ODK_URL)
            SelfRegistrationInvitation.initiate_workflow(
                self.domain,
                [SelfRegistrationUserInfo('999123')],
                app_id=self.app_id,
                android_only=True,
                custom_first_message='Sign up here: {}',
            )

        self.assertLastOutgoingSMS('+999123', [
            'Sign up here: {}'.format(DUMMY_REGISTRATION_URL),
            '[commcare app - do not delete] {}'.format(DUMMY_APP_INFO_URL_B64),
        ])

    def test_resend_install_link(self):
        self.domain_obj.sms_mobile_worker_registration_enabled = True
        self.domain_obj.enable_registration_welcome_sms_for_mobile_worker = True
        self.domain_obj.save()

        with patch.object(SelfRegistrationInvitation, 'get_app_info_url', return_value=DUMMY_APP_INFO_URL):
            success_numbers, invalid_format_numbers, error_numbers = SelfRegistrationInvitation.send_install_link(
                self.domain,
                [SelfRegistrationUserInfo('999123')],
                self.app_id
            )
            self.assertEqual(success_numbers, ['999123'])
            self.assertEqual(invalid_format_numbers, [])
            self.assertEqual(error_numbers, [])

        self.assertLastOutgoingSMS('+999123', [
            _MESSAGES[MSG_REGISTRATION_INSTALL_COMMCARE].format(GOOGLE_PLAY_STORE_COMMCARE_URL),
            '[commcare app - do not delete] {}'.format(DUMMY_APP_INFO_URL_B64),
        ])

    def test_resend_install_link_with_custom_message(self):
        self.domain_obj.sms_mobile_worker_registration_enabled = True
        self.domain_obj.enable_registration_welcome_sms_for_mobile_worker = True
        self.domain_obj.save()

        with patch.object(SelfRegistrationInvitation, 'get_app_info_url', return_value=DUMMY_APP_INFO_URL):
            success_numbers, invalid_format_numbers, error_numbers = SelfRegistrationInvitation.send_install_link(
                self.domain,
                [SelfRegistrationUserInfo('999123')],
                self.app_id,
                custom_message='Click here to reinstall CommCare: {}'
            )
            self.assertEqual(success_numbers, ['999123'])
            self.assertEqual(invalid_format_numbers, [])
            self.assertEqual(error_numbers, [])

        self.assertLastOutgoingSMS('+999123', [
            'Click here to reinstall CommCare: {}'.format(GOOGLE_PLAY_STORE_COMMCARE_URL),
            '[commcare app - do not delete] {}'.format(DUMMY_APP_INFO_URL_B64),
        ])


class RegistrationAPITestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(RegistrationAPITestCase, cls).setUpClass()
        Role.get_cache().clear()
        generator.instantiate_accounting()

        cls.domain1, cls.account1, cls.subscription1 = cls.setup_domain('reg-api-test-1')
        cls.domain2, cls.account2, cls.subscription2 = cls.setup_domain('reg-api-test-2')

        cls.admin_user1 = cls.setup_webuser('admin@reg-api-test-1', cls.domain1, 'admin')
        cls.read_only_user1 = cls.setup_webuser('readonly@reg-api-test-1', cls.domain1, 'read-only')
        cls.admin_user2 = cls.setup_webuser('admin@reg-api-test-2', cls.domain2, 'admin')

    @classmethod
    def setup_domain(cls, name):
        domain_obj = Domain(name=name, sms_mobile_worker_registration_enabled=True)
        domain_obj.save()

        plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        account = BillingAccount.get_or_create_account_by_domain(
            name, created_by="automated-test-" + cls.__name__
        )[0]
        subscription = Subscription.new_domain_subscription(account, name, plan)
        subscription.is_active = True
        subscription.save()

        domain_obj = Domain.get(domain_obj.get_id)
        return (domain_obj, account, subscription)

    @classmethod
    def setup_webuser(cls, username, domain, role):
        user = WebUser.create(domain.name, username, '{}-password'.format(username))
        user.set_role(domain.name, role)
        user.save()
        return user

    @classmethod
    def tearDownClass(cls):
        SubscriptionAdjustment.objects.all().delete()

        for obj in [
            cls.subscription1,
            cls.account1,
            cls.admin_user1,
            cls.read_only_user1,
            cls.domain1,
            cls.subscription2,
            cls.account2,
            cls.admin_user2,
            cls.domain2,
        ]:
            obj.delete()

        super(RegistrationAPITestCase, cls).tearDownClass()

    def setUp(self):
        PhoneNumber.objects.all().delete()

    def tearDown(self):
        SelfRegistrationInvitation.objects.all().delete()
        PhoneNumber.objects.all().delete()

    def make_api_post(self, domain, username, password, payload):
        c = Client()
        auth = 'Basic ' + base64.b64encode('{}:{}'.format(username, password))
        return c.post('/a/{}/api/v0_5/sms_user_registration/'.format(domain.name), json.dumps(payload),
            HTTP_AUTHORIZATION=auth, content_type='application/json')

    @patch('corehq.apps.sms.resources.v0_5.UserSelfRegistrationValidation._validate_app_id', new=noop)
    def test_auth(self):

        with patch.object(SelfRegistrationInvitation, 'initiate_workflow', return_value=([], [], [])):

            payload = {'app_id': '123', 'users': [{'phone_number': '999123'}]}

            # test wrong creds, right permission, right domain
            response = self.make_api_post(self.domain1, 'admin@reg-api-test-1',
                'wrong-password', payload)
            self.assertEqual(response.status_code, 401)

            # test right creds, right permission, right domain
            response = self.make_api_post(self.domain1, 'admin@reg-api-test-1',
                'admin@reg-api-test-1-password', payload)
            self.assertEqual(response.status_code, 200)

            # test right creds, wrong permission, right domain
            response = self.make_api_post(self.domain1, 'readonly@reg-api-test-1',
                'readonly@reg-api-test-1-password', payload)
            self.assertEqual(response.status_code, 403)

            # test right creds, right permission, wrong domain
            response = self.make_api_post(self.domain1, 'admin@reg-api-test-2',
                'admin@reg-api-test-2-password', payload)
            self.assertEqual(response.status_code, 403)

            # test right creds, right permission, right domain, for different domain
            response = self.make_api_post(self.domain2, 'admin@reg-api-test-2',
                'admin@reg-api-test-2-password', payload)
            self.assertEqual(response.status_code, 200)

    @patch('corehq.apps.sms.resources.v0_5.UserSelfRegistrationValidation._validate_app_id', new=noop)
    def test_parameter_passing(self):

        with patch.object(SelfRegistrationInvitation, 'initiate_workflow', return_value=([], [], [])) as init:

            response = self.make_api_post(
                self.domain1,
                'admin@reg-api-test-1',
                'admin@reg-api-test-1-password',
                {
                    'app_id': '123',
                    'users': [{'phone_number': '999123'}],
                },
            )
            self.assertEqual(response.status_code, 200)
            init.assert_called_once_with(
                self.domain1.name,
                [SelfRegistrationUserInfo('999123')],
                app_id='123',
                custom_first_message=None,
                android_only=False,
                require_email=False,
            )

        with patch.object(SelfRegistrationInvitation, 'initiate_workflow', return_value=([], [], [])) as init:

            response = self.make_api_post(
                self.domain1,
                'admin@reg-api-test-1',
                'admin@reg-api-test-1-password',
                {
                    'app_id': '123',
                    'users': [
                        {'phone_number': '999123',
                         'custom_user_data': {'abc': 'def'}}
                    ]
                },
            )
            self.assertEqual(response.status_code, 200)
            init.assert_called_once_with(
                self.domain1.name,
                [SelfRegistrationUserInfo('999123', {'abc': 'def'})],
                app_id='123',
                custom_first_message=None,
                android_only=False,
                require_email=False,
            )

        with patch.object(SelfRegistrationInvitation, 'initiate_workflow', return_value=([], [], [])) as init:

            response = self.make_api_post(
                self.domain1,
                'admin@reg-api-test-1',
                'admin@reg-api-test-1-password',
                {
                    'app_id': '123',
                    'users': [{'phone_number': '999123'}],
                    'android_only': True,
                },
            )
            self.assertEqual(response.status_code, 200)
            init.assert_called_once_with(
                self.domain1.name,
                [SelfRegistrationUserInfo('999123')],
                app_id='123',
                custom_first_message=None,
                android_only=True,
                require_email=False,
            )

        with patch.object(SelfRegistrationInvitation, 'initiate_workflow', return_value=([], [], [])) as init:

            response = self.make_api_post(
                self.domain1,
                'admin@reg-api-test-1',
                'admin@reg-api-test-1-password',
                {
                    'app_id': '123',
                    'users': [{'phone_number': '999123'}],
                    'require_email': True,
                },
            )
            self.assertEqual(response.status_code, 200)
            init.assert_called_once_with(
                self.domain1.name,
                [SelfRegistrationUserInfo('999123')],
                app_id='123',
                custom_first_message=None,
                android_only=False,
                require_email=True,
            )

        with patch.object(SelfRegistrationInvitation, 'initiate_workflow', return_value=([], [], [])) as init:

            response = self.make_api_post(
                self.domain1,
                'admin@reg-api-test-1',
                'admin@reg-api-test-1-password',
                {
                    'app_id': '123',
                    'users': [{'phone_number': '999123'}],
                    'custom_registration_message': 'Hello',
                },
            )
            self.assertEqual(response.status_code, 200)
            init.assert_called_once_with(
                self.domain1.name,
                [SelfRegistrationUserInfo('999123')],
                app_id='123',
                custom_first_message='Hello',
                android_only=False,
                require_email=False,
            )

    @patch('corehq.apps.sms.resources.v0_5.UserSelfRegistrationValidation._validate_app_id', new=noop)
    def test_validation(self):

        with patch.object(SelfRegistrationInvitation, 'initiate_workflow', return_value=([], [], [])):
            response = self.make_api_post(
                self.domain1,
                'admin@reg-api-test-1',
                'admin@reg-api-test-1-password',
                {},
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content, '{"sms_user_registration": {"app_id": "This field is required"}}')

            response = self.make_api_post(
                self.domain1,
                'admin@reg-api-test-1',
                'admin@reg-api-test-1-password',
                {'app_id': 123},
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content,
                '{"sms_user_registration": {"app_id": "Expected type: basestring"}}')

            response = self.make_api_post(
                self.domain1,
                'admin@reg-api-test-1',
                'admin@reg-api-test-1-password',
                {'app_id': '123'},
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content, '{"sms_user_registration": {"users": "This field is required"}}')

            response = self.make_api_post(
                self.domain1,
                'admin@reg-api-test-1',
                'admin@reg-api-test-1-password',
                {'app_id': '123', 'users': [{}]},
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content,
                '{"sms_user_registration": {"phone_number": "This field is required"}}')
