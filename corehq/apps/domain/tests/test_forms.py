from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.models import (
    Domain,
    OperatorCallLimitSettings,
    SMSAccountConfirmationSettings,
)
from corehq.toggles import NAMESPACE_DOMAIN, TWO_STAGE_USER_PROVISIONING_BY_SMS
from corehq.toggles.shortcuts import set_toggle

from .. import forms
from ..forms import (
    ConfirmSubscriptionRenewalForm,
    DomainGlobalSettingsForm,
    PrivacySecurityForm,
)


class PrivacySecurityFormTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        patcher = patch.object(forms, 'domain_has_privilege')
        self.mock_domain_has_privilege = patcher.start()
        self.mock_domain_has_privilege.return_value = False
        self.addCleanup(patcher.stop)

    def test_visible_fields(self):
        form = self.create_form()
        visible_field_names = self.get_visible_fields(form)
        self.assertEqual(visible_field_names, [
            'restrict_superusers',
            'secure_submissions',
            'allow_domain_requests',
            'disable_mobile_login_lockout',
            'allow_invite_email_only'
        ])

    @patch.object(forms.HIPAA_COMPLIANCE_CHECKBOX, 'enabled', return_value=True)
    def test_hippa_compliance_toggle(self, mock_toggle):
        form = self.create_form()
        visible_field_names = self.get_visible_fields(form)
        self.assertIn('hipaa_compliant', visible_field_names)

    @patch.object(forms.SECURE_SESSION_TIMEOUT, 'enabled', return_value=True)
    def test_secure_session_timeout(self, mock_toggle):
        form = self.create_form()
        visible_field_names = self.get_visible_fields(form)
        self.assertIn('secure_sessions_timeout', visible_field_names)

    def test_advanced_domain_security(self):
        self.mock_domain_has_privilege.return_value = True
        form = self.create_form()
        visible_field_names = self.get_visible_fields(form)
        advanced_security_fields = {'ga_opt_out', 'strong_mobile_passwords', 'two_factor_auth', 'secure_sessions'}
        self.assertTrue(advanced_security_fields.issubset(set(visible_field_names)))

    def create_form(self):
        return PrivacySecurityForm(user_name='test_user', domain='test_domain')

    def get_visible_fields(self, form):
        fieldset = form.helper.layout.fields[0]
        return [field[0] for field in fieldset.fields]


class TestDomainGlobalSettingsForm(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.domain = Domain.generate_name('test_domain')
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()
        self.call_settings = OperatorCallLimitSettings(domain=self.domain)
        self.call_settings.save()
        self.account_confirmation_settings = SMSAccountConfirmationSettings.get_settings(self.domain)

    def test_confirmation_link_expiry_not_present_when_flag_not_set(self):
        set_toggle(TWO_STAGE_USER_PROVISIONING_BY_SMS.slug, self.domain_obj, False, namespace=NAMESPACE_DOMAIN)
        form = self.create_form()
        self.assertTrue('confirmation_link_expiry' not in form.fields)

    def test_confirmation_link_expiry_default_present_when_flag_set(self):
        set_toggle(TWO_STAGE_USER_PROVISIONING_BY_SMS.slug, self.domain, True, namespace=NAMESPACE_DOMAIN)
        form = self.create_form(
            confirmation_link_expiry=self.account_confirmation_settings.confirmation_link_expiry_time,
            confirmation_sms_project_name=self.account_confirmation_settings.project_name)
        form.full_clean()
        form.save(Mock(), self.domain_obj)
        self.assertTrue('confirmation_link_expiry' in form.fields)
        self.assertEqual(14, self.account_confirmation_settings.confirmation_link_expiry_time)

    def test_confirmation_link_expiry_custom_present_when_flag_set(self):
        set_toggle(TWO_STAGE_USER_PROVISIONING_BY_SMS.slug, self.domain, True, namespace=NAMESPACE_DOMAIN)
        form = self.create_form(
            confirmation_link_expiry=25,
            confirmation_sms_project_name=self.account_confirmation_settings.project_name)
        form.full_clean()
        form.save(Mock(), self.domain_obj)
        self.assertTrue('confirmation_link_expiry' in form.fields)
        settings_obj = SMSAccountConfirmationSettings.get_settings(self.domain)
        self.assertEqual(25, settings_obj.confirmation_link_expiry_time)

    def test_confirmation_link_expiry_error_when_invalid_value(self):
        OperatorCallLimitSettings.objects.all().delete()
        set_toggle(TWO_STAGE_USER_PROVISIONING_BY_SMS.slug, self.domain, True, namespace=NAMESPACE_DOMAIN)
        form = self.create_form(
            confirmation_link_expiry='abc',
            confirmation_sms_project_name=self.account_confirmation_settings.project_name)
        form.full_clean()
        self.assertEqual(1, len(form.errors))
        self.assertEqual(['Enter a whole number.'], form.errors.get("confirmation_link_expiry"))

    def test_confirmation_link_expiry_error_when_value_less_than_lower_limit(self):
        OperatorCallLimitSettings.objects.all().delete()
        set_toggle(TWO_STAGE_USER_PROVISIONING_BY_SMS.slug, self.domain, True, namespace=NAMESPACE_DOMAIN)
        form = self.create_form(
            confirmation_link_expiry='-1',
            confirmation_sms_project_name=self.account_confirmation_settings.project_name)
        form.full_clean()
        self.assertEqual(1, len(form.errors))
        self.assertEqual(["Ensure this value is greater than or equal to 1."],
                         form.errors.get("confirmation_link_expiry"))

    def test_confirmation_link_expiry_error_when_value_more_than_upper_limit(self):
        OperatorCallLimitSettings.objects.all().delete()
        set_toggle(TWO_STAGE_USER_PROVISIONING_BY_SMS.slug, self.domain, True, namespace=NAMESPACE_DOMAIN)
        form = self.create_form(
            confirmation_link_expiry='31',
            confirmation_sms_project_name=self.account_confirmation_settings.project_name)
        form.full_clean()
        self.assertEqual(1, len(form.errors))
        self.assertEqual(["Ensure this value is less than or equal to 30."],
                         form.errors.get("confirmation_link_expiry"))

    def test_operator_call_limit_not_present_when_domain_not_eligible(self):
        OperatorCallLimitSettings.objects.all().delete()
        form = self.create_form()
        self.assertTrue('operator_call_limit' not in form.fields)

    def test_operator_call_limit_default_present_when_domain_eligible(self):
        form = self.create_form(
            domain=self.domain_obj, operator_call_limit=OperatorCallLimitSettings.CALL_LIMIT_DEFAULT)
        form.full_clean()
        form.save(Mock(), self.domain_obj)
        self.assertTrue('operator_call_limit' in form.fields)
        self.assertEqual(120, OperatorCallLimitSettings.objects.get(domain=self.domain_obj.name).call_limit)

    def test_operator_call_limit_custom_present_when_domain_eligible(self):
        form = self.create_form(domain=self.domain_obj, operator_call_limit=50)
        form.full_clean()
        form.save(Mock(), self.domain_obj)
        self.assertTrue('operator_call_limit' in form.fields)
        self.assertEqual(50, OperatorCallLimitSettings.objects.get(domain=self.domain_obj.name).call_limit)

    def test_operator_call_limit_error_when_invalid_value(self):
        form = self.create_form(domain=self.domain_obj, operator_call_limit="12a")
        form.full_clean()
        form.save(Mock(), self.domain_obj)
        self.assertTrue('operator_call_limit' in form.fields)
        self.assertIsNotNone(form.errors)
        self.assertEqual(1, len(form.errors))
        self.assertEqual(['Enter a whole number.'], form.errors.get("operator_call_limit"))

    def test_operator_call_limit_error_when_value_less_than_lower_limit(self):
        form = self.create_form(domain=self.domain_obj, operator_call_limit="0")
        form.full_clean()
        form.save(Mock(), self.domain_obj)
        self.assertTrue('operator_call_limit' in form.fields)
        self.assertIsNotNone(form.errors)
        self.assertEqual(1, len(form.errors))
        self.assertEqual(['Ensure this value is greater than or equal to 1.'],
                         form.errors.get("operator_call_limit"))

    def test_operator_call_limit_error_when_value_more_than_higher_limit(self):
        form = self.create_form(domain=self.domain_obj, operator_call_limit="1001")
        form.full_clean()
        form.save(Mock(), self.domain_obj)
        self.assertTrue('operator_call_limit' in form.fields)
        self.assertIsNotNone(form.errors)
        self.assertEqual(1, len(form.errors))
        self.assertEqual(['Ensure this value is less than or equal to 1000.'],
                         form.errors.get("operator_call_limit"))

    def create_form(self, domain=None, **kwargs):
        data = {
            "hr_name": "foo",
            "project_description": "sample",
            "default_timezone": "UTC",
        }
        if kwargs:
            for field, value in kwargs.items():
                data.update({field: value})
        if not domain:
            domain = self.domain_obj
        return DomainGlobalSettingsForm(data, domain=domain)

    def tearDown(self):
        set_toggle(TWO_STAGE_USER_PROVISIONING_BY_SMS.slug, self.domain, False, namespace=NAMESPACE_DOMAIN)
        self.domain_obj.delete()
        OperatorCallLimitSettings.objects.all().delete()
        SMSAccountConfirmationSettings.objects.all().delete()
        super().tearDown()


class TestAppReleaseModeSettingForm(TestCase):

    def setUp(self) -> None:
        domain = Domain.generate_name('test_domain')
        self.domain_obj = Domain(name=domain)
        self.domain_obj.save()

    def test_release_mode_settings_visible_and_saved_without_error(self):
        # Create form
        data = {
            "hr_name": "foo",
            "project_description": "sample",
            "default_timezone": "UTC",
        }
        form = DomainGlobalSettingsForm(data, domain=self.domain_obj)

        self.assertTrue('release_mode_visibility' in form.fields)

        form.full_clean()
        saved = form.save(Mock(), self.domain_obj)
        self.assertEqual(True, saved)  # No error during form save


class TestConfirmSubscriptionRenewalForm(TestCase):
    def setUp(self):
        super().setUp()
        self.domain = generator.arbitrary_domain()
        self.user = generator.arbitrary_user(self.domain.name, is_webuser=True, is_admin=True)
        self.account = generator.billing_account(self.user, self.user.name)
        self.subscription = generator.generate_domain_subscription(
            self.account, self.domain, datetime.today(), datetime.today() + timedelta(days=7), is_active=True
        )

    def tearDown(self):
        self.user.delete(self.domain.name, deleted_by=None)
        self.domain.delete()
        clear_plan_version_cache()
        super().tearDown()

    def create_form_for_submission(self, new_plan_version):
        # initialize form to set initial values
        form = self.create_form(new_plan_version)
        form_data = form.data

        # populate fields with initial values
        form_data.update(**{key: form[key].value() for key in form.fields})
        return self.create_form(new_plan_version, data=form_data)

    def create_form(self, new_plan_version, **kwargs):
        args = (self.account, self.domain, self.user, self.subscription, new_plan_version)
        return ConfirmSubscriptionRenewalForm(*args, **kwargs)

    def test_form_initial_values(self):
        next_plan_version = self.subscription.plan_version
        form = self.create_form(next_plan_version)

        self.assertEqual(form['plan_edition'].value(), next_plan_version.plan.edition)
        self.assertFalse(form['is_annual_plan'].value())

    def test_form_renews_same_subscription(self):
        next_plan_version = self.subscription.plan_version
        form = self.create_form_for_submission(next_plan_version)
        form.save()

        self.assertTrue(form.is_valid())
        self.assertTrue(self.subscription.is_renewed)
        self.assertEqual(self.subscription.next_subscription.plan_version, next_plan_version)

    def test_form_renews_alternate_subscription(self):
        next_plan_version = DefaultProductPlan.get_default_plan_version(
            edition=SoftwarePlanEdition.STANDARD,
            is_annual_plan=True,
        )
        form = self.create_form_for_submission(next_plan_version)
        form.save()

        self.assertTrue(form.is_valid())
        self.assertTrue(self.subscription.is_renewed)
        self.assertEqual(self.subscription.next_subscription.plan_version, next_plan_version)
