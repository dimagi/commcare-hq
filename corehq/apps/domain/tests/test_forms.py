from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock

from django.test import SimpleTestCase, TestCase

from dateutil.relativedelta import relativedelta

from corehq.apps.accounting.const import (
    SUBSCRIPTION_PREPAY_MIN_DAYS_UNTIL_DUE,
    PAY_ANNUALLY_SUBSCRIPTION_MONTHS,
)
from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    WirePrepaymentInvoice,
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
    ConfirmNewSubscriptionForm,
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


class BaseTestSubscriptionForm(TestCase):
    def setUp(self):
        super().setUp()
        self.domain = generator.arbitrary_domain()
        self.user = generator.arbitrary_user(self.domain.name, is_webuser=True, is_admin=True)
        self.account = generator.billing_account(self.user, self.user.name)

    def tearDown(self):
        self.user.delete(self.domain.name, deleted_by=None)
        self.domain.delete()
        clear_plan_version_cache()
        super().tearDown()

    def create_form_for_submission(self, *args):
        # initialize form to set initial values
        form = self.create_form(*args)
        form_data = form.data

        # populate fields with initial values
        form_data.update(**{key: form[key].value() for key in form.fields})
        return self.create_form(*args, data=form_data)

    def create_form(self, *args, **kwargs):
        raise NotImplementedError


class TestConfirmNewSubscriptionForm(BaseTestSubscriptionForm):
    def setUp(self):
        super().setUp()
        self.subscription = generator.generate_domain_subscription(
            self.account, self.domain, date.today(), None,
            plan_version=DefaultProductPlan.get_default_plan_version(), is_active=True,
        )

    def create_form(self, new_plan_version, **kwargs):
        args = (self.account, self.domain.name, self.user, new_plan_version, self.subscription)
        return ConfirmNewSubscriptionForm(*args, **kwargs)

    def test_form_initial_values(self):
        plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.STANDARD)
        form = self.create_form(plan_version)
        self.assertEqual(form['plan_edition'].value(), plan_version.plan.edition)

    def test_pay_monthly_subscription(self):
        new_plan_version = DefaultProductPlan.get_default_plan_version(
            SoftwarePlanEdition.STANDARD, is_annual_plan=False
        )
        form = self.create_form_for_submission(new_plan_version)
        form.save()
        self.assertTrue(form.is_valid())
        self.assertEqual(self.subscription.date_end, date.today())

        new_subscription = Subscription.get_active_subscription_by_domain(self.domain)
        self.assertEqual(new_subscription.plan_version, new_plan_version)
        self.assertEqual(new_subscription.date_start, date.today())
        self.assertIsNone(new_subscription.date_end)

    def test_pay_annually_subscription(self):
        new_plan_version = DefaultProductPlan.get_default_plan_version(
            SoftwarePlanEdition.STANDARD, is_annual_plan=True
        )
        form = self.create_form_for_submission(new_plan_version)
        form.save()
        self.assertTrue(form.is_valid())
        self.assertEqual(self.subscription.date_end, date.today())

        new_subscription = Subscription.get_active_subscription_by_domain(self.domain)
        self.assertEqual(new_subscription.plan_version, new_plan_version)
        self.assertEqual(new_subscription.date_start, date.today())
        self.assertEqual(new_subscription.date_end, new_subscription.date_start + relativedelta(years=1))

    def test_pay_annually_creates_prepayment_invoice(self):
        new_plan_version = DefaultProductPlan.get_default_plan_version(
            SoftwarePlanEdition.STANDARD, is_annual_plan=True
        )
        form = self.create_form_for_submission(new_plan_version)
        form.save()
        self.assertTrue(form.is_valid())

        prepayment_invoice = WirePrepaymentInvoice.objects.get(domain=self.domain.name)
        new_subscription = Subscription.get_active_subscription_by_domain(self.domain)
        self.assertEqual(prepayment_invoice.date_start, new_subscription.date_start)
        self.assertEqual(prepayment_invoice.date_end, new_subscription.date_end)
        self.assertEqual(prepayment_invoice.date_due,
                         date.today() + timedelta(days=SUBSCRIPTION_PREPAY_MIN_DAYS_UNTIL_DUE))
        self.assertEqual(prepayment_invoice.balance,
                         new_plan_version.product_rate.monthly_fee * PAY_ANNUALLY_SUBSCRIPTION_MONTHS)

    def test_downgrade_minimum_subscription_length(self):
        self.subscription.delete()
        old_plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.PRO)
        old_date_start = date.today()
        self.subscription = generator.generate_domain_subscription(
            self.account, self.domain, old_date_start, None, plan_version=old_plan_version, is_active=True,
        )

        new_plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.STANDARD)
        form = self.create_form_for_submission(new_plan_version)
        form.save()
        self.assertTrue(form.is_valid())
        self.assertEqual(self.subscription.date_end, old_date_start + timedelta(days=30))

        next_subscription = self.subscription.next_subscription
        self.assertEqual(next_subscription.plan_version, new_plan_version)
        self.assertEqual(next_subscription.date_start, old_date_start + timedelta(days=30))


class TestConfirmSubscriptionRenewalForm(BaseTestSubscriptionForm):
    def setUp(self):
        super().setUp()
        self.subscription = generator.generate_domain_subscription(
            self.account, self.domain, date.today(), date.today() + timedelta(days=7), is_active=True
        )

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


class TestUsernameOrEmailField(SimpleTestCase):
    def setUp(self):
        self.field = forms.UsernameOrEmailField()

    def test_valid_email_address(self):
        valid_emails = ['test@example.com', 'user.name@domain.org',
                        'admin+tag@subdomain.example.co.uk']
        for email in valid_emails:
            with self.subTest(email=email):
                self.field.validate(email)

    def test_valid_username(self):
        valid_usernames = ['username', 'user123', 'user_name', 'user-name']
        for username in valid_usernames:
            with self.subTest(username=username):
                self.field.validate(username)

    def test_invalid_email_format(self):
        invalid_emails = ['@example.com', 'user@', 'user@@example.com', 'user name@example.com']
        for email in invalid_emails:
            with self.subTest(email=email):
                with self.assertRaises(forms.ValidationError):
                    self.field.validate(email)


class TestHQPasswordResetForm(SimpleTestCase):
    def setUp(self):
        self.get_active_users_patcher = patch('corehq.apps.domain.forms.get_active_users_by_email')
        self.mock_get_active_users = self.get_active_users_patcher.start()

        self.send_email_patcher = patch('corehq.apps.domain.forms.send_html_email_async')
        self.mock_send_email = self.send_email_patcher.start()

    def tearDown(self):
        self.get_active_users_patcher.stop()
        self.send_email_patcher.stop()

    @patch('corehq.apps.domain.forms.get_user_model')
    def test_valid_email_submission(self, mock_get_user_model):
        mock_user = MagicMock(is_active=True, password='somepassword')
        mock_manager = MagicMock(filter=MagicMock(return_value=[mock_user]))
        mock_user_model = MagicMock(_default_manager=mock_manager)
        mock_get_user_model.return_value = mock_user_model

        form_data = {'email': 'test@example.com'}
        form = forms.HQPasswordResetForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_username_like_input_validation(self):
        form_data = {'email': 'username'}
        form = forms.HQPasswordResetForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('username', form.errors['email'][0].lower())

    def test_invalid_email_format(self):
        form_data = {'email': 'invalid.email'}
        form = forms.HQPasswordResetForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_empty_email_field(self):
        form_data = {'email': ''}
        form = forms.HQPasswordResetForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class TestDomainPasswordResetForm(SimpleTestCase):
    def setUp(self):
        self.domain = 'test-domain'

        self.get_user_model_patcher = patch('corehq.apps.domain.forms.get_user_model')
        self.mock_get_user_model = self.get_user_model_patcher.start()

        self.mock_user = MagicMock(is_active=True, password='somepassword')
        self.mock_manager = MagicMock(filter=MagicMock(return_value=[self.mock_user]))
        self.mock_user_model = MagicMock(_default_manager=self.mock_manager)
        self.mock_get_user_model.return_value = self.mock_user_model

        self.get_active_users_patcher = patch('corehq.apps.domain.forms.get_active_users_by_email')
        self.mock_get_active_users = self.get_active_users_patcher.start()

        self.generate_username_patcher = patch('corehq.apps.domain.forms.generate_mobile_username')
        self.mock_generate_username = self.generate_username_patcher.start()

        self.send_email_patcher = patch('corehq.apps.domain.forms.send_html_email_async')
        self.mock_send_email = self.send_email_patcher.start()

    def tearDown(self):
        self.get_user_model_patcher.stop()
        self.get_active_users_patcher.stop()
        self.generate_username_patcher.stop()
        self.send_email_patcher.stop()

    def test_valid_email_submission(self):
        form_data = {'email': 'test@example.com'}
        form = forms.DomainPasswordResetForm(data=form_data, domain=self.domain)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['email'], 'test@example.com')

    def test_valid_username_submission(self):
        """Test form with valid username (gets converted to mobile username)."""
        form_data = {'email': 'testuser'}
        self.mock_generate_username.return_value = 'testuser@test-domain.commcarehq.org'

        form = forms.DomainPasswordResetForm(data=form_data, domain=self.domain)
        self.assertTrue(form.is_valid())

        self.mock_generate_username.assert_called_once_with('testuser', self.domain, False)
        self.assertEqual(form.cleaned_data['email'], 'testuser@test-domain.commcarehq.org')

    def test_clean_email_handles_email_input(self):
        form_data = {'email': 'test@example.com'}
        form = forms.DomainPasswordResetForm(data=form_data, domain=self.domain)
        form.full_clean()

        self.mock_generate_username.assert_not_called()

    def test_clean_email_handles_username_input(self):
        form_data = {'email': 'testuser'}
        self.mock_generate_username.return_value = 'testuser@test-domain.commcarehq.org'

        form = forms.DomainPasswordResetForm(data=form_data, domain=self.domain)
        form.full_clean()

        self.mock_generate_username.assert_called_once_with('testuser', self.domain, False)

    def test_save_method_calls_get_active_users_with_domain(self):
        form_data = {'email': 'test@example.com'}
        form = forms.DomainPasswordResetForm(data=form_data, domain=self.domain)
        self.assertTrue(form.is_valid())

        mock_request = Mock()
        form.save(request=mock_request)

        self.mock_get_active_users.assert_called_once_with('test@example.com', self.domain)

    def test_invalid_email_format(self):
        form_data = {'email': 'invalid@email@format.com'}
        form = forms.DomainPasswordResetForm(data=form_data, domain=self.domain)
        self.assertFalse(form.is_valid())


class TestConfidentialDomainPasswordResetForm(SimpleTestCase):
    def setUp(self):
        self.domain = 'test-domain'

        self.get_active_users_patcher = patch('corehq.apps.domain.forms.get_active_users_by_email')
        self.mock_get_active_users = self.get_active_users_patcher.start()

        self.generate_username_patcher = patch('corehq.apps.domain.forms.generate_mobile_username')
        self.mock_generate_username = self.generate_username_patcher.start()

        self.send_email_patcher = patch('corehq.apps.domain.forms.send_html_email_async')
        self.mock_send_email = self.send_email_patcher.start()

    def tearDown(self):
        self.get_active_users_patcher.stop()
        self.generate_username_patcher.stop()
        self.send_email_patcher.stop()

    def test_clean_email_suppresses_validation_errors(self):
        with patch.object(forms.HQPasswordResetForm, 'clean_email') as mock_parent_clean:
            mock_parent_clean.side_effect = forms.ValidationError("User does not exist")

            form_data = {'email': 'nonexistent@example.com'}
            form = forms.ConfidentialPasswordResetForm(data=form_data)
            form.full_clean()

        with patch.object(forms.DomainPasswordResetForm, 'clean_email') as mock_parent_clean:
            mock_parent_clean.side_effect = forms.ValidationError("User does not exist")

            form_data = {'email': 'nonexistent@example.com'}
            form = forms.ConfidentialDomainPasswordResetForm(data=form_data, domain=self.domain)
            form.full_clean()


class TestPasswordResetFormsNoAutocompleteMixin(SimpleTestCase):
    @patch('corehq.apps.domain.forms.settings')
    def test_confidential_forms_autocomplete(self, mock_settings):
        mock_settings.DISABLE_AUTOCOMPLETE_ON_SENSITIVE_FORMS = True
        form1 = forms.ConfidentialPasswordResetForm()
        self.assertEqual(form1.fields['email'].widget.attrs.get('autocomplete'), 'off')
        form2 = forms.ConfidentialDomainPasswordResetForm(domain='test')
        self.assertEqual(form2.fields['email'].widget.attrs.get('autocomplete'), 'off')

        mock_settings.DISABLE_AUTOCOMPLETE_ON_SENSITIVE_FORMS = False
        form1 = forms.ConfidentialPasswordResetForm()
        self.assertNotEqual(form1.fields['email'].widget.attrs.get('autocomplete'), 'off')
        form2 = forms.ConfidentialDomainPasswordResetForm(domain='test')
        self.assertNotEqual(form2.fields['email'].widget.attrs.get('autocomplete'), 'off')


class TestConstructAppDownloadLinkForm(SimpleTestCase):
    def test_clean_app_url_with_valid_production_server(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['source_server'], 'production')
        self.assertEqual(form.cleaned_data['source_domain'], 'test-domain')
        self.assertEqual(form.cleaned_data['app_id'], '62891a383516c656850cc9c7e7b8d459')

    def test_clean_app_url_with_valid_india_server(self):
        url = 'https://india.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['source_server'], 'india')
        self.assertEqual(form.cleaned_data['source_domain'], 'test-domain')
        self.assertEqual(form.cleaned_data['app_id'], '62891a383516c656850cc9c7e7b8d459')

    def test_clean_app_url_with_valid_eu_server(self):
        url = 'https://eu.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['source_server'], 'eu')
        self.assertEqual(form.cleaned_data['source_domain'], 'test-domain')
        self.assertEqual(form.cleaned_data['app_id'], '62891a383516c656850cc9c7e7b8d459')

    def test_clean_app_url_without_trailing_slash(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['source_server'], 'production')
        self.assertEqual(form.cleaned_data['source_domain'], 'test-domain')
        self.assertEqual(form.cleaned_data['app_id'], '62891a383516c656850cc9c7e7b8d459')

    def test_clean_app_url_with_additional_path_segments(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/settings/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['source_server'], 'production')
        self.assertEqual(form.cleaned_data['source_domain'], 'test-domain')
        self.assertEqual(form.cleaned_data['app_id'], '62891a383516c656850cc9c7e7b8d459')

    def test_clean_app_url_with_http_protocol(self):
        url = 'http://www.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertFalse(form.is_valid())
        self.assertIn('The URL must start with https://', str(form.errors['app_url']))

    def test_clean_app_url_with_invalid_server(self):
        url = 'https://invalid.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertFalse(form.is_valid())
        self.assertIn('The URL must be from a valid CommCare server', str(form.errors['app_url']))

    @patch('corehq.apps.domain.forms.settings.SERVER_ENVIRONMENT', 'production')
    def test_clean_app_url_same_server_validation(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertFalse(form.is_valid())
        self.assertIn('The source app url is in the same server as current server', str(form.errors['app_url']))

    @patch('corehq.apps.domain.forms.settings.SERVER_ENVIRONMENT', 'india')
    def test_clean_app_url_different_server_validation(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['source_server'], 'production')

    def test_clean_app_url_missing_path_segments(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertFalse(form.is_valid())
        self.assertIn('Invalid app URL format', str(form.errors['app_url']))

    def test_clean_app_url_invalid_path_structure(self):
        url = 'https://www.commcarehq.org/b/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertFalse(form.is_valid())
        self.assertIn('Invalid app URL format', str(form.errors['app_url']))

    def test_clean_app_url_missing_apps_segment(self):
        url = 'https://www.commcarehq.org/a/test-domain/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertFalse(form.is_valid())
        self.assertIn('Invalid app URL format', str(form.errors['app_url']))

    def test_clean_app_url_missing_view_segment(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertFalse(form.is_valid())
        self.assertIn('Invalid app URL format', str(form.errors['app_url']))

    def test_clean_app_url_invalid_app_id_format(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/invalid-app-id/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertFalse(form.is_valid())
        self.assertIn('Invalid app URL format', str(form.errors['app_url']))

    def test_clean_app_url_with_query_parameters(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/?param=value'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['source_server'], 'production')
        self.assertEqual(form.cleaned_data['source_domain'], 'test-domain')
        self.assertEqual(form.cleaned_data['app_id'], '62891a383516c656850cc9c7e7b8d459')

    def test_clean_app_url_with_fragment(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/#section'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['source_server'], 'production')
        self.assertEqual(form.cleaned_data['source_domain'], 'test-domain')
        self.assertEqual(form.cleaned_data['app_id'], '62891a383516c656850cc9c7e7b8d459')

    def test_clean_app_url_with_forms_open_in_app(self):
        url = 'https://www.commcarehq.org/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/form/'
        '545858ed6a3449ccb377ba6f0c8a3c61/source/#form/name'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['source_server'], 'production')
        self.assertEqual(form.cleaned_data['source_domain'], 'test-domain')
        self.assertEqual(form.cleaned_data['app_id'], '62891a383516c656850cc9c7e7b8d459')

    def test_clean_app_url_with_port_number(self):
        url = 'https://www.commcarehq.org:443/a/test-domain/apps/view/62891a383516c656850cc9c7e7b8d459/'
        form = forms.ConstructAppDownloadLinkForm(data={'app_url': url})
        self.assertFalse(form.is_valid())
        self.assertIn('The URL must be from a valid CommCare server', str(form.errors['app_url']))
