import os
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.http.response import Http404, HttpResponse
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.client import RequestFactory
from django.urls import reverse

from django_otp.plugins.otp_totp.models import TOTPDevice
from two_factor.views import ProfileView, SetupView
from two_factor.plugins.phonenumber.views import PhoneSetupView

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models import UserHistory, WebUser, HQApiKey
from corehq.const import USER_CHANGE_VIA_WEB
from corehq.tests.util.artifact import artifact
from corehq.util.tests.test_utils import disable_quickcache
from corehq.apps.sso.models import IdentityProvider, AuthenticatedEmailDomain
from corehq.apps.sso.tests import generator

from .. import views
from ..views import (
    ApiKeyView,
    EnableMobilePrivilegesView,
    TwoFactorPhoneSetupView,
    TwoFactorProfileView,
    TwoFactorResetView,
    TwoFactorSetupView,
    get_qrcode,
)


class EnableMobilePrivilegesViewTests(SimpleTestCase):

    def test_qr_code(self):
        """
        Check that the qr code in the context is a string, as opposed to a byte object
        """
        view = EnableMobilePrivilegesView()
        view.get_context_data = Mock(return_value={})
        view.render_to_response = lambda x: x
        mock_request = Mock()
        mock_request.user.username = "test"

        with patch('corehq.apps.settings.views.sign', lambda x: b'foo'):
            context = view.get(mock_request)

        self.assertTrue(isinstance(context['qrcode_64'], str))


@override_settings(ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE=True)
class TwoFactorProfileView_Context_Tests(SimpleTestCase):
    @override_settings(ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE=False)
    def test_phone_methods_do_not_display_when_settings_are_disabled(self):
        user = self._create_user(two_factor_enabled=True, belongs_to_messaging_domain=True)
        view = self._create_view_for_user(user)
        context = view.get_context_data()
        self.assertFalse(context['allow_phone_2fa'])

    def test_phone_methods_display_when_user_belongs_to_messaging_domain(self):
        user = self._create_user(two_factor_enabled=True, belongs_to_messaging_domain=True)
        view = self._create_view_for_user(user)
        context = view.get_context_data()
        self.assertTrue(context['allow_phone_2fa'])

    def test_phone_methods_do_not_display_when_user_does_not_belong_to_messaging_domain(self):
        user = self._create_user(two_factor_enabled=True, belongs_to_messaging_domain=False)
        view = self._create_view_for_user(user)
        context = view.get_context_data()
        self.assertFalse(context['allow_phone_2fa'])

    def test_phone_methods_display_when_user_has_previous_backup_phones(self):
        user = self._create_user(
            two_factor_enabled=True,
            belongs_to_messaging_domain=False,
            has_backup_phones=True)
        view = self._create_view_for_user(user)
        context = view.get_context_data()
        self.assertTrue(context['allow_phone_2fa'])

    def setUp(self):
        self.factory = RequestFactory()
        self.two_factor_enabled = False
        self.backup_phones = []
        mock_2fa_context_patcher = patch.object(ProfileView, 'get_context_data')
        mock_2fa_context = mock_2fa_context_patcher.start()
        mock_2fa_context.side_effect = lambda: ({
            'default_device': self.two_factor_enabled,
            'backup_phones': self.backup_phones
        })

        self.addCleanup(mock_2fa_context_patcher.stop)

    def _create_user(self, two_factor_enabled=True, belongs_to_messaging_domain=True, has_backup_phones=False):
        user = Mock(is_authenticated=True, is_active=True)
        user.belongs_to_messaging_domain.return_value = belongs_to_messaging_domain
        self.two_factor_enabled = two_factor_enabled
        if has_backup_phones:
            self.backup_phones = ['phone1', 'phone2']
        return user

    def _create_view_for_user(self, user):
        request = self.factory.get('/some_url')
        request.user = request.couch_user = user
        view = TwoFactorProfileView()
        view.setup(request)
        return view


@override_settings(ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE=True)
class TwoFactorSetupView_FormKwargs_Tests(SimpleTestCase):
    @override_settings(ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE=False)
    def test_phone_methods_are_prohibited_when_settings_are_disabled(self):
        user = self._create_user(belongs_to_messaging_domain=True)
        view = self._create_view_for_user(user)
        self.assertFalse(view.get_form_kwargs(step='method')['allow_phone_2fa'])

    def test_phone_methods_are_allowed_when_user_belongs_to_messaging_domain(self):
        user = self._create_user(belongs_to_messaging_domain=True)
        view = self._create_view_for_user(user)
        self.assertTrue(view.get_form_kwargs(step='method')['allow_phone_2fa'])

    def test_phone_methods_are_prohibited_when_user_does_not_belongs_to_messaging_domain(self):
        user = self._create_user(belongs_to_messaging_domain=False)
        view = self._create_view_for_user(user)
        self.assertFalse(view.get_form_kwargs(step='method')['allow_phone_2fa'])

    def setUp(self):
        self.factory = RequestFactory()
        mock_2fa_form_kwargs_patcher = patch.object(SetupView, 'get_form_kwargs', return_value={})
        mock_2fa_form_kwargs_patcher.start()

        self.addCleanup(mock_2fa_form_kwargs_patcher.stop)

    def _create_user(self, belongs_to_messaging_domain=True):
        user = Mock(is_authenticated=True, is_active=True)
        user.belongs_to_messaging_domain.return_value = belongs_to_messaging_domain
        return user

    def _create_view_for_user(self, user):
        request = self.factory.post('/some_url')
        request.user = request.couch_user = user
        view = TwoFactorSetupView()
        view.setup(request)

        return view


@override_settings(ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE=True)
class TwoFactorPhoneSetupViewTests(SimpleTestCase):
    @override_settings(ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE=False)
    def test_when_settings_are_disabled_view_returns_404(self):
        user = self._create_user(belongs_to_messaging_domain=True)
        with self.assertRaises(Http404):
            self._call_view(user)

    def test_when_user_belongs_to_messaging_domain_returns_200(self):
        user = self._create_user(belongs_to_messaging_domain=True)
        response = self._call_view(user)
        self.assertEqual(response.status_code, 200)

    def test_when_user_does_not_belong_to_messaging_domain_returns_404(self):
        user = self._create_user(belongs_to_messaging_domain=False)
        with self.assertRaises(Http404):
            self._call_view(user)

    def test_when_user_has_grandfathered_phones_returns_200(self):
        # Even if domain access has been shut off, we still want to show the user his phones
        user = self._create_user(belongs_to_messaging_domain=False, has_backup_phones=True)
        response = self._call_view(user)

        self.assertEqual(response.status_code, 200)

    def setUp(self):
        self.factory = RequestFactory()
        mock_parent_dispatch = patch.object(PhoneSetupView, 'dispatch', return_value=HttpResponse(status=200))
        mock_parent_dispatch.start()

        self.addCleanup(mock_parent_dispatch.stop)

    def _create_user(self, belongs_to_messaging_domain=True, has_backup_phones=False):
        user = Mock(is_authenticated=True, is_active=True)
        user.belongs_to_messaging_domain.return_value = belongs_to_messaging_domain

        if has_backup_phones:
            # NOTE: This is not intended to be used multiple times in the same test
            backup_phone_patcher = patch.object(views, 'backup_phones',
                return_value=['phone1', 'phone2'])  # Only matters that it isn't empty
            backup_phone_patcher.start()
            self.addCleanup(backup_phone_patcher.stop)
        return user

    def _call_view(self, user):
        request = self.factory.post('/some_url')
        request.user = request.couch_user = user
        view = TwoFactorPhoneSetupView.as_view()
        return view(request)


class ApiKeyViewTests(TestCase):
    def test_user_with_no_identity_provider_cannot_view_full_api_keys(self):
        couch_user = self.create_user('test')
        HQApiKey.objects.create(user=couch_user.get_django_user(), name='test-key', key='1234567890')
        request = self.create_request_for_user(couch_user)
        view = ApiKeyView()
        view.request = request

        displayed_key = list(view.paginated_list)[0]['itemData']

        self.assertNotIn('full_key', displayed_key)

    def test_user_with_identity_provider_that_allows_full_keys_can_see_full_key(self):
        couch_user = self.create_user('test@test.com')
        HQApiKey.objects.create(user=couch_user.get_django_user(), name='test-key', key='1234567890')

        self.create_idp('test.com', always_show_user_api_keys=True)

        request = self.create_request_for_user(couch_user)

        view = ApiKeyView()
        view.request = request

        displayed_key = list(view.paginated_list)[0]['itemData']

        self.assertEqual(displayed_key['full_key'], '1234567890')

    def test_user_managed_by_identity_provider_that_forbids_full_keys_cannot_see_full_key(self):
        couch_user = self.create_user('test@test.com')
        HQApiKey.objects.create(user=couch_user.get_django_user(), name='test-key', key='1234567890')

        self.create_idp('test.com', always_show_user_api_keys=False)

        request = self.create_request_for_user(couch_user)

        view = ApiKeyView()
        view.request = request

        displayed_key = list(view.paginated_list)[0]['itemData']

        self.assertNotIn('full_key', displayed_key)

    def setUp(self):
        super().setUp()
        patcher = patch.object(WebUser, 'get_time_zone', new=lambda self: 'UTC')
        patcher.start()
        self.addCleanup(patcher.stop)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.billing_account = generator.get_billing_account_for_idp()

    def create_user(self, username):
        couch_user = WebUser.create(None, username, 'password', None, None)
        self.addCleanup(couch_user.delete, None, None)
        return couch_user

    def create_request_for_user(self, user):
        request = RequestFactory().get('/some_url')
        request.couch_user = user
        request.user = user.get_django_user()
        return request

    def create_idp(self, domain, always_show_user_api_keys=False):
        idp = IdentityProvider.objects.create(
            name='test-idp',
            slug='test-idp',
            owner=self.billing_account,
            is_active=True,
            always_show_user_api_keys=always_show_user_api_keys
        )
        AuthenticatedEmailDomain.objects.create(email_domain=domain, identity_provider=idp)
        return idp


class TestMyAccountSettingsView(TestCase):
    domain_name = 'test'

    def setUp(self):
        super().setUp()
        self.domain = create_domain(self.domain_name)
        self.couch_user = WebUser.create(None, "test", "foobar", None, None)
        self.couch_user.add_domain_membership(self.domain_name, is_admin=True)
        self.couch_user.save()

        self.url = reverse('my_account_settings')
        self.client.login(username='test', password='foobar')

    def tearDown(self):
        self.couch_user.delete(self.domain_name, deleted_by=None)
        self.domain.delete()
        super().tearDown()

    def test_process_delete_phone_number(self):
        phone_number = "9999999999"
        self.client.post(
            self.url,
            {"form_type": "delete-phone-number", "phone_number": phone_number}
        )

        user_history_log = UserHistory.objects.get(user_id=self.couch_user.get_id)
        self.assertIsNone(user_history_log.message)
        self.assertEqual(user_history_log.change_messages, UserChangeMessage.phone_numbers_removed([phone_number]))
        self.assertEqual(user_history_log.changed_by, self.couch_user.get_id)
        self.assertIsNone(user_history_log.by_domain)
        self.assertIsNone(user_history_log.for_domain)
        self.assertEqual(user_history_log.changed_via, USER_CHANGE_VIA_WEB)


@disable_quickcache
class TestQrCode(SimpleTestCase):
    """Generates a URL QR code PNG file and ensures it matches the reference
    file that exists in version control.

    This tests against updates to the ``qrcode`` dependency to ensure library
    updates don't break rendered QR code images.

    It is possible that new versions of ``qrcode`` could result in different PNG
    content (causing this test to fail), but the resulting PNG still being a
    valid QR code. If this happens, use the ``create_test_qr_codes``
    management command to generate a new reference PNG and verify that it works
    as expected.
    """
    TEST_QR_CODE_FILE = os.path.join(os.path.dirname(__file__), "data", "qrcode_url.png")
    TEST_QR_CODE_TEXT = "https://www.commcarehq.org/"

    def test_get_qrcode(self):
        reference_fpath = self.TEST_QR_CODE_FILE  # use a local var to improve readability
        rendered_bytes = get_qrcode(self.TEST_QR_CODE_TEXT)
        with (
            open(reference_fpath, "rb") as reference_png,
            artifact(os.path.basename(reference_fpath), BytesIO(rendered_bytes)),
        ):
            self.assertEqual(
                reference_png.read(),
                rendered_bytes,
                f"Rendered PNG differs from expected reference: {reference_fpath}",
            )


class TestTwoFactorResetView(TestCase):

    def test_default_device_is_deleted(self):
        default_device = TOTPDevice.objects.create(user=self.couch_user.get_django_user(), name='default')
        self._call_view(self.couch_user)
        with self.assertRaises(TOTPDevice.DoesNotExist):
            TOTPDevice.objects.get(id=default_device.id)

    def test_backup_device_is_not_deleted(self):
        backup_device = TOTPDevice.objects.create(user=self.couch_user.get_django_user(), name='backup')
        self._call_view(self.couch_user)
        # should not raise error
        TOTPDevice.objects.get(id=backup_device.id)

    def _call_view(self, user):
        request = self.factory.get('/some_url')
        request.user = user.get_django_user()
        request.couch_user = user

        def get_response(request):
            return {}

        middleware = SessionMiddleware(get_response)
        middleware.process_request(request)
        request.session.save()
        view = TwoFactorResetView.as_view()
        return view(request)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain('two-factor-domain')
        cls.addClassCleanup(cls.domain.delete)
        cls.couch_user = WebUser.create(cls.domain.name, 'test@user.com', 'abc123', None, None)
        cls.addClassCleanup(cls.couch_user.delete, None, None)

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
