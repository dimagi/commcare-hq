from django.test import SimpleTestCase
from unittest.mock import Mock, patch
from corehq.apps.domain.models import Domain, OperatorCallLimitSettings
from corehq import privileges

from ..forms import DomainGlobalSettingsForm, DomainMetadataForm, PrivacySecurityForm
from .. import forms


class PrivacySecurityFormTests(SimpleTestCase):

    def test_visible_fields(self):
        form = self._create_form()
        visible_field_names = self._get_visible_fields(form)
        self.assertEqual(visible_field_names, [
            'restrict_superusers',
            'secure_submissions',
            'allow_domain_requests',
            'disable_mobile_login_lockout'
        ])

    @patch.object(forms.RESTRICT_MOBILE_ACCESS, 'enabled', return_value=True)
    def test_restrict_mobile_access_toggle(self, mock_toggle):
        form = self._create_form()
        visible_field_names = self._get_visible_fields(form)
        self.assertIn('restrict_mobile_access', visible_field_names)

    @patch.object(forms.HIPAA_COMPLIANCE_CHECKBOX, 'enabled', return_value=True)
    def test_hippa_compliance_toggle(self, mock_toggle):
        form = self._create_form()
        visible_field_names = self._get_visible_fields(form)
        self.assertIn('hipaa_compliant', visible_field_names)

    @patch.object(forms.SECURE_SESSION_TIMEOUT, 'enabled', return_value=True)
    def test_secure_session_timeout(self, mock_toggle):
        form = self._create_form()
        visible_field_names = self._get_visible_fields(form)
        self.assertIn('secure_sessions_timeout', visible_field_names)

    def test_advanced_domain_security(self):
        self.mock_domain_has_privilege.return_value = True
        form = self._create_form()
        visible_field_names = self._get_visible_fields(form)
        advanced_security_fields = {'ga_opt_out', 'strong_mobile_passwords', 'two_factor_auth', 'secure_sessions'}
        self.assertTrue(advanced_security_fields.issubset(set(visible_field_names)))

# Helpers
    def setUp(self):
        super().setUp()
        patcher = patch.object(forms, 'domain_has_privilege')
        self.mock_domain_has_privilege = patcher.start()
        self.mock_domain_has_privilege.return_value = False
        self.addCleanup(patcher.stop)

    def _create_form(self):
        return PrivacySecurityForm(user_name='test_user', domain='test_domain')

    def _get_visible_fields(self, form):
        fieldset = form.helper.layout.fields[0]
        return [field[0] for field in fieldset.fields]


class DomainGlobalSettingsFormTests(SimpleTestCase):
    def test_all_visible_fields(self):
        form = self._create_form()
        self.assertEqual([
            'hr_name',
            'project_description',
            'default_timezone',
            'default_geocoder_location',
            'logo',
            'delete_logo',
            'call_center_enabled',
            'call_center_type',
            'call_center_case_owner',
            'call_center_case_type',
            'mobile_ucr_sync_interval',
            'confirmation_link_expiry'
        ], form.get_visible_field_names())

    def test_if_cannot_use_custom_logo_logo_fields_are_removed(self):
        form = self._create_form(can_use_custom_logo=False)

        visible_fields = form.get_visible_field_names()
        self.assertNotIn('logo', visible_fields)
        self.assertNotIn('delete_logo', visible_fields)

    def test_if_call_center_config_disabled_call_center_fields_are_removed(self):
        self.domain = self._create_domain(call_center_config_enabled=False)
        form = self._create_form()

        visible_fields = form.get_visible_field_names()
        self.assertNotIn('call_center_enabled', visible_fields)
        self.assertNotIn('call_center_type', visible_fields)
        self.assertNotIn('call_center_case_owner', visible_fields)
        self.assertNotIn('call_center_case_type', visible_fields)

    def test_if_mobile_ucr_disabled_sync_field_is_removed(self):
        self.ucr_toggle_enabled = False
        form = self._create_form()

        self.assertNotIn('mobile_ucr_sync_interval', form.get_visible_field_names())

    def test_if_sms_user_provisioning_disabled_field_is_removed(self):
        self.sms_user_provisioning_toggle_enabled = False
        form = self._create_form()

        self.assertNotIn('confirmation_link_expiry', form.get_visible_field_names())

    def test_confirmation_link_expiry_error_when_invalid_value(self):
        self.sms_user_provisioning_toggle_enabled = True
        form = self._create_form(confirmation_link_expiry='abc')
        form.full_clean()
        self.assertEqual({'confirmation_link_expiry': ['Enter a whole number.']}, form.errors)

    def test_save_writes_confirmation_link_expiry(self):
        domain_obj = self._create_domain(confirmation_link_expiry_time=500)
        form = self._create_form(confirmation_link_expiry=100)
        form.save(Mock(), domain_obj)
        self.assertEqual(100, domain_obj.confirmation_link_expiry_time)
        domain_obj.save.assert_called()

    def test_operator_call_limit_not_present_when_domain_not_eligible(self):
        self.mock_call_limit_settings.values_list.return_value = []  # No domain has call limit settings
        form = self._create_form()
        self.assertNotIn('operator_call_limit', form.get_visible_field_names())

    def test_operator_call_limit_field_configured_with_all_values(self):
        call_settings = OperatorCallLimitSettings(domain=self.domain.name, call_limit=50)
        self.mock_call_limit_settings.values_list.return_value = [self.domain.name]
        self.mock_call_limit_settings.get.return_value = call_settings

        form = self._create_form()

        self.assertIn('operator_call_limit', form.get_visible_field_names())
        self.assertEqual(form.fields['operator_call_limit'].initial, 50)
        self.assertEqual(form.fields['operator_call_limit'].min_value, 1)
        self.assertEqual(form.fields['operator_call_limit'].max_value, 1000)

    def test_operator_call_limit_error_when_invalid_value(self):
        call_settings = OperatorCallLimitSettings(domain=self.domain.name, call_limit=50)
        self.mock_call_limit_settings.values_list.return_value = [self.domain.name]
        self.mock_call_limit_settings.get.return_value = call_settings

        form = self._create_form(operator_call_limit='12a')
        form.full_clean()
        self.assertEqual({'operator_call_limit': ['Enter a whole number.']}, form.errors)

    def test_save_writes_call_limit(self):
        call_settings = OperatorCallLimitSettings(domain=self.domain.name, call_limit=50)
        call_settings.save = Mock()
        self.mock_call_limit_settings.values_list.return_value = [self.domain.name]
        self.mock_call_limit_settings.get.return_value = call_settings

        form = self._create_form(operator_call_limit=95)
        form.save(Mock(), self.domain)

        self.assertEqual(call_settings.call_limit, 95)
        call_settings.save.assert_called()

# Helpers
    def setUp(self):
        super().setUp()

        domain_patcher = patch.object(Domain, 'save')
        domain_patcher.start()
        self.addCleanup(domain_patcher.stop)

        self.domain = self._create_domain()
        self.ucr_toggle_enabled = True
        self.sms_user_provisioning_toggle_enabled = True

        mock_ucr_toggle = patch.object(forms.MOBILE_UCR, 'enabled',
            side_effect=lambda domain: self.ucr_toggle_enabled)
        mock_ucr_toggle.start()
        self.addCleanup(mock_ucr_toggle.stop)

        mock_sms_provisioning_toggle = patch.object(forms.TWO_STAGE_USER_PROVISIONING_BY_SMS, 'enabled',
            side_effect=lambda domain: self.sms_user_provisioning_toggle_enabled)
        mock_sms_provisioning_toggle.start()
        self.addCleanup(mock_sms_provisioning_toggle.stop)

        mock_get_domain_by_name = patch.object(Domain, 'get_by_name', return_value=self.domain)
        mock_get_domain_by_name.start()
        self.addCleanup(mock_get_domain_by_name.stop)

        mock_call_limit_domain_patcher = patch.object(OperatorCallLimitSettings,
            'objects')
        self.mock_call_limit_settings = mock_call_limit_domain_patcher.start()
        self.mock_call_limit_settings.values_list.return_value = []
        self.addCleanup(mock_call_limit_domain_patcher.stop)

    def _create_form(self, can_use_custom_logo=True, **kwargs):
        data = {
            'hr_name': 'foo',
            'project_description': 'sample',
            'default_timezone': 'UTC',
            'confirmation_link_expiry': 500
        }
        data.update(**kwargs)
        return DomainGlobalSettingsForm(
            data, domain=self.domain, can_use_custom_logo=can_use_custom_logo)

    def _create_domain(self, call_center_config_enabled=True, **kwargs):
        domain_properties = {
            'name': 'test-domain',
            'confirmation_link_expiry_time': 500,
            'call_center_enabled': False,
            'default_timezone': 'UTC'
        }
        domain_properties.update(kwargs)
        domain_obj = Domain(**domain_properties)
        domain_obj.call_center_config.enabled = call_center_config_enabled
        return domain_obj


class DomainMetadataFormTests(SimpleTestCase):
    def test_all_visible_fields(self):
        form = self._create_form()
        visible_fields = form.get_visible_field_names()
        self.assertIn('cloudcare_releases', visible_fields)
        self.assertIn('default_geocoder_location', visible_fields)

    def test_no_cloudcare_privilege_hides_cloudcare_releases_field(self):
        self.domain_privileges.remove(privileges.CLOUDCARE)
        form = self._create_form()
        self.assertNotIn('cloudcare_releases', form.get_visible_field_names())

    def test_default_cloudcare_releases_hides_cloudcare_releases_field(self):
        self.domain.cloudcare_releases = 'default'
        form = self._create_form()
        self.assertNotIn('cloudcare_releases', form.get_visible_field_names())

    def test_no_privilege_removes_geocoder_field(self):
        self.domain_privileges.remove(privileges.GEOCODER)
        form = self._create_form()
        self.assertNotIn('default_geocoder_location', form.get_visible_field_names())

# Helpers
    def setUp(self):
        super().setUp()
        privilege_patcher = patch.object(forms, 'domain_has_privilege')
        self.mock_domain_has_privilege = privilege_patcher.start()
        self.mock_domain_has_privilege.side_effect = self._domain_has_privilege
        self.addCleanup(privilege_patcher.stop)

        self.domain_privileges = [privileges.CLOUDCARE, privileges.GEOCODER]

        self.domain = self._create_domain()

        mock_call_limit_domain_patcher = patch.object(OperatorCallLimitSettings,
            'objects')
        mock_call_limit_settings = mock_call_limit_domain_patcher.start()
        mock_call_limit_settings.values_list.return_value = []
        self.addCleanup(mock_call_limit_domain_patcher.stop)

    def _create_form(self):
        return DomainMetadataForm(domain=self.domain)

    def _domain_has_privilege(self, domain, privilege):
        return privilege in self.domain_privileges

    def _create_domain(self, call_center_config_enabled=True, **kwargs):
        domain_properties = {
            'name': 'test-domain',
            'confirmation_link_expiry_time': 500,
            'cloudcare_releases': 'stars',
        }
        domain_properties.update(kwargs)
        domain_obj = Domain(**domain_properties)
        domain_obj.call_center_config.enabled = call_center_config_enabled
        return domain_obj
