from datetime import datetime, timedelta
from mock import patch

from django import forms
from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.sso.forms import (
    CreateIdentityProviderForm,
    EditIdentityProviderAdminForm,
    SSOEnterpriseSettingsForm,
)
from corehq.apps.sso.models import (
    IdentityProvider,
    AuthenticatedEmailDomain,
    UserExemptFromSingleSignOn,
)
from corehq.apps.sso.tests import generator
from corehq.apps.users.models import WebUser


class BaseSSOFormTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()
        cls.domain = Domain.get_or_create_with_name(
            "vaultwax-001",
            is_active=True
        )
        cls.accounting_admin = WebUser.create(
            cls.domain.name, 'jadmin@dimagi.com', 'testpwd', None, None
        )

    @classmethod
    def tearDownClass(cls):
        cls.accounting_admin.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        cls.account.delete()
        super().tearDownClass()


class TestCreateIdentityProviderForm(BaseSSOFormTest):

    @classmethod
    def tearDownClass(cls):
        IdentityProvider.objects.all().delete()
        super().tearDownClass()

    def test_bad_slug_is_invalid(self):
        """
        Ensure that a poorly formatted slug raises a ValidationError and the
        CreateIdentityProviderForm does not validate.
        """
        post_data = {
            'owner': self.account.id,
            'name': 'test idp',
            'slug': 'bad slug',
        }
        create_idp_form = CreateIdentityProviderForm(post_data)
        create_idp_form.cleaned_data = post_data
        with self.assertRaises(forms.ValidationError):
            create_idp_form.clean_slug()
        self.assertFalse(create_idp_form.is_valid())

    def test_created_identity_provider(self):
        """
        Ensure that a valid CreateIdentityProviderForm successfully creates an
        IdentityProvider.
        """
        post_data = {
            'owner': self.account.id,
            'name': 'Azure AD for Vault Wax',
            'slug': 'vaultwax',
        }
        create_idp_form = CreateIdentityProviderForm(post_data)
        self.assertTrue(create_idp_form.is_valid())
        create_idp_form.create_identity_provider(self.accounting_admin)

        idp = IdentityProvider.objects.get(owner=self.account)
        self.assertEqual(idp.owner, self.account)
        self.assertEqual(idp.slug, post_data['slug'])
        self.assertEqual(idp.name, post_data['name'])
        self.assertIsNotNone(idp.sp_cert_public)
        self.assertIsNotNone(idp.sp_cert_private)
        self.assertIsNotNone(idp.date_sp_cert_expiration)
        self.assertEqual(idp.created_by, self.accounting_admin.username)
        self.assertEqual(idp.last_modified_by, self.accounting_admin.username)


@patch('corehq.apps.sso.utils.url_helpers.get_dashboard_link', return_value='#')
class TestEditIdentityProviderAdminForm(BaseSSOFormTest):

    def setUp(self):
        super().setUp()
        self.idp = IdentityProvider.objects.create(
            owner=self.account,
            name='Azure AD for Vault Wax',
            slug='vaultwax',
            created_by='otheradmin@dimagi.com',
            last_modified_by='otheradmin@dimagi.com',
        )
        self.idp.create_service_provider_certificate()

    def tearDown(self):
        UserExemptFromSingleSignOn.objects.all().delete()
        AuthenticatedEmailDomain.objects.all().delete()
        IdentityProvider.objects.all().delete()
        super().tearDown()

    def _fulfill_all_active_requirements(self, except_entity_id=False, except_login_url=False,
                                         except_logout_url=False, except_certificate=False,
                                         except_certificate_date=False):
        self.idp.entity_id = None if except_entity_id else 'https://test.org/metadata'
        self.idp.login_url = None if except_login_url else 'https://test.org/sls'
        self.idp.logout_url = None if except_logout_url else 'https://test.org/slo'
        self.idp.idp_cert_public = None if except_certificate else 'TEST CERTIFICATE'
        self.idp.date_idp_cert_expiration = (None if except_certificate_date
                                             else datetime.utcnow() + timedelta(days=30))
        self.idp.save()

    def _get_post_data(self, name=None, is_editable=False, is_active=False, slug=None):
        return {
            'name': name if name is not None else self.idp.name,
            'is_editable': is_editable,
            'is_active': is_active,
            'slug': slug or self.idp.slug,
        }

    def test_bad_slug_update_is_invalid(self, *args):
        """
        Ensure that if passed a bad slug, EditIdentityProviderAdminForm raises
        a ValidationError and does not validate.
        """
        post_data = self._get_post_data(slug='bad slug')
        edit_idp_form = EditIdentityProviderAdminForm(self.idp, post_data)
        edit_idp_form.cleaned_data = post_data
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_slug()
        self.assertFalse(edit_idp_form.is_valid())

    def test_slug_update_conflict(self, *args):
        """
        Ensure that if another IdentityProvider exists with the same slug,
        EditIdentityProviderAdminForm raises a ValidationError and does not
        validate.
        """
        second_idp = IdentityProvider.objects.create(
            owner=self.account,
            name='Azure AD for VWX',
            slug='vwx',
            created_by='otheradmin@dimagi.com',
            last_modified_by='otheradmin@dimagi.com',
        )
        post_data = self._get_post_data(slug=second_idp.slug)
        edit_idp_form = EditIdentityProviderAdminForm(self.idp, post_data)
        edit_idp_form.cleaned_data = post_data
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_slug()
        self.assertFalse(edit_idp_form.is_valid())

    def test_slug_and_last_modified_by_updates(self, *args):
        """
        Ensure that the `slug` and `last_modified_by` fields properly update
        when EditIdentityProviderAdminForm validates and calls
        update_identity_provider().
        """
        post_data = self._get_post_data(slug='vaultwax-2')
        edit_idp_form = EditIdentityProviderAdminForm(self.idp, post_data)
        self.assertTrue(edit_idp_form.is_valid())
        edit_idp_form.update_identity_provider(self.accounting_admin)

        idp = IdentityProvider.objects.get(id=self.idp.id)
        self.assertEqual(idp.slug, post_data['slug'])
        self.assertEqual(idp.last_modified_by, self.accounting_admin.username)
        self.assertNotEqual(idp.created_by, self.accounting_admin.username)

    def test_name_updates_and_is_required(self, *args):
        """
        Ensure that the `name` field is both required and updates the name
        of the IdentityProvider when EditIdentityProviderAdminForm
        validates and update_identity_provider() is called.
        """
        bad_post_data = self._get_post_data(name='')
        bad_edit_idp_form = EditIdentityProviderAdminForm(self.idp, bad_post_data)
        self.assertFalse(bad_edit_idp_form.is_valid())

        post_data = self._get_post_data(name='new name test')
        edit_idp_form = EditIdentityProviderAdminForm(self.idp, post_data)
        self.assertTrue(edit_idp_form.is_valid())
        edit_idp_form.update_identity_provider(self.accounting_admin)

        idp = IdentityProvider.objects.get(id=self.idp.id)
        self.assertEqual(idp.name, post_data['name'])

    def test_is_editable_has_met_requirements_and_value_updates(self, *args):
        """
        Ensure that the requirements for `is_editable` are met in order for
        EditIdentityProviderAdminForm to validate and that once it is valid,
        calling update_identity_provider() updates the `is_editable` field on
        the IdentityProvider as expected.
        """
        post_data = self._get_post_data(is_editable=True)
        edit_idp_form = EditIdentityProviderAdminForm(self.idp, post_data)
        edit_idp_form.cleaned_data = post_data
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_editable()

        email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.com',
        )
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_editable()

        UserExemptFromSingleSignOn.objects.create(
            username='b@vaultwax.com',
            email_domain=email_domain,
        )
        self.assertTrue(edit_idp_form.is_valid())
        edit_idp_form.update_identity_provider(self.accounting_admin)

        idp = IdentityProvider.objects.get(id=self.idp.id)
        self.assertTrue(idp.is_editable)

    def test_is_active_has_met_requirements_and_value_updates(self, *args):
        """
        Ensure that the requirements for `is_active` are met in order for
        EditIdentityProviderAdminForm to validate and that once it is valid,
        calling update_identity_provider() updates the `is_active` field on
        the IdentityProvider as expected.
        """
        post_data = self._get_post_data(is_active=True)
        edit_idp_form = EditIdentityProviderAdminForm(self.idp, post_data)
        edit_idp_form.cleaned_data = post_data

        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_active()

        email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.com',
        )
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_active()

        UserExemptFromSingleSignOn.objects.create(
            username='b@vaultwax.com',
            email_domain=email_domain,
        )
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_active()

        self._fulfill_all_active_requirements(except_entity_id=True)
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_active()

        self._fulfill_all_active_requirements(except_login_url=True)
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_active()

        self._fulfill_all_active_requirements(except_logout_url=True)
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_active()

        self._fulfill_all_active_requirements(except_certificate=True)
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_active()

        self._fulfill_all_active_requirements(except_certificate_date=True)
        with self.assertRaises(forms.ValidationError):
            edit_idp_form.clean_is_active()

        self._fulfill_all_active_requirements()
        self.assertTrue(edit_idp_form.is_valid())
        edit_idp_form.update_identity_provider(self.accounting_admin)

        idp = IdentityProvider.objects.get(id=self.idp.id)
        self.assertTrue(idp.is_active)


class TestSSOEnterpriseSettingsForm(BaseSSOFormTest):

    def setUp(self):
        super().setUp()
        self.idp = IdentityProvider.objects.create(
            owner=self.account,
            name='Azure AD for Vault Wax',
            slug='vaultwax',
            created_by='otheradmin@dimagi.com',
            last_modified_by='otheradmin@dimagi.com',
        )
        self.idp.is_editable = True
        self.idp.create_service_provider_certificate()

    def tearDown(self):
        UserExemptFromSingleSignOn.objects.all().delete()
        AuthenticatedEmailDomain.objects.all().delete()
        IdentityProvider.objects.all().delete()
        super().tearDown()

    @staticmethod
    def _get_post_data(no_entity_id=False, no_login_url=False, no_logout_url=False,
                       is_active=False, require_encrypted_assertions=False,
                       certificate=None):
        return {
            'is_active': is_active,
            'entity_id': '' if no_entity_id else 'https://test.org/metadata',
            'login_url': '' if no_login_url else 'https://test.org/sls',
            'logout_url': '' if no_logout_url else 'https://test.org/slo',
            'require_encrypted_assertions': require_encrypted_assertions,
            'idp_cert_public': certificate,
        }

    @staticmethod
    def _get_request_files(cert_file):
        return {
            'idp_cert_public': cert_file,
        }

    def test_is_active_triggers_form_validation_errors(self):
        """
        Test that if `is_active` is set to true, then related required fields
        raise ValidationErrors if left blank. Once the requirements are met and
        SSOEnterpriseSettingsForm validates, ensure that
        update_identity_provider() updates the `is_active` field on
        the IdentityProvider as expected.
        """
        post_data = self._get_post_data(
            is_active=True,
            no_entity_id=True,
            no_login_url=True,
            no_logout_url=True,
        )
        edit_sso_idp_form = SSOEnterpriseSettingsForm(self.idp, post_data)
        edit_sso_idp_form.cleaned_data = post_data

        with self.assertRaises(forms.ValidationError):
            edit_sso_idp_form.clean_is_active()

        email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.com',
        )
        with self.assertRaises(forms.ValidationError):
            edit_sso_idp_form.clean_is_active()

        UserExemptFromSingleSignOn.objects.create(
            username='b@vaultwax.com',
            email_domain=email_domain,
        )
        # should not raise exception now
        edit_sso_idp_form.clean_is_active()

        with self.assertRaises(forms.ValidationError):
            edit_sso_idp_form.clean_entity_id()
        with self.assertRaises(forms.ValidationError):
            edit_sso_idp_form.clean_login_url()
        with self.assertRaises(forms.ValidationError):
            edit_sso_idp_form.clean_logout_url()
        with self.assertRaises(forms.ValidationError):
            edit_sso_idp_form.clean_idp_cert_public()
        self.assertFalse(edit_sso_idp_form.is_valid())

    def test_that_is_active_updates_successfully_when_requirements_are_met(self):
        """
        Ensure that update_identity_provider() updates the `is_active` field on
        the IdentityProvider as expected when requirements are met.
        """
        email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.com',
        )
        UserExemptFromSingleSignOn.objects.create(
            username='b@vaultwax.com',
            email_domain=email_domain,
        )

        certificate_file = generator.get_public_cert_file()
        post_data = self._get_post_data(
            is_active=True,
            certificate=certificate_file,
        )

        self.assertFalse(self.idp.is_active)
        edit_sso_idp_form = SSOEnterpriseSettingsForm(
            self.idp, post_data, self._get_request_files(certificate_file)
        )
        edit_sso_idp_form.cleaned_data = post_data
        self.assertTrue(edit_sso_idp_form.is_valid())

        edit_sso_idp_form.update_identity_provider(self.accounting_admin)

        idp = IdentityProvider.objects.get(id=self.idp.id)
        self.assertTrue(idp.is_editable)
        self.assertTrue(idp.is_active)
        self.assertEqual(idp.entity_id, post_data['entity_id'])
        self.assertEqual(idp.login_url, post_data['login_url'])
        self.assertEqual(idp.logout_url, post_data['logout_url'])
        certificate_file.seek(0)
        self.assertEqual(idp.idp_cert_public, certificate_file.read().decode('utf-8'))
        self.assertIsNotNone(idp.date_idp_cert_expiration)

    def test_that_validation_error_is_raised_when_certificate_file_is_bad(self):
        """
        Ensure that SSOEnterpriseSettingsForm raises a validation error
        when the certificate file contains bad data.
        """
        certificate_file = generator.get_bad_cert_file(b"bad cert")
        post_data = self._get_post_data(certificate=certificate_file)

        edit_sso_idp_form = SSOEnterpriseSettingsForm(
            self.idp, post_data, self._get_request_files(certificate_file)
        )
        edit_sso_idp_form.cleaned_data = post_data

        with self.assertRaises(forms.ValidationError):
            edit_sso_idp_form.clean_idp_cert_public()

    def test_that_validation_error_is_raised_when_certificate_is_expired(self):
        """
        Ensure that SSOEnterpriseSettingsForm raises a validation error
        when the certificate file contains an expired certificate.
        """
        certificate_file = generator.get_public_cert_file(expiration_in_seconds=0)
        post_data = self._get_post_data(certificate=certificate_file)

        edit_sso_idp_form = SSOEnterpriseSettingsForm(
            self.idp, post_data, self._get_request_files(certificate_file)
        )

        edit_sso_idp_form.cleaned_data = post_data

        with self.assertRaises(forms.ValidationError):
            edit_sso_idp_form.clean_idp_cert_public()

    def test_last_modified_by_and_fields_update_when_not_active(self):
        """
        Ensure that fields properly update and that `last_modified_by` updates
        as expected when SSOEnterpriseSettingsForm validates and
        update_identity_provider() is called.
        """
        email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.com',
        )
        UserExemptFromSingleSignOn.objects.create(
            username='b@vaultwax.com',
            email_domain=email_domain,
        )
        post_data = self._get_post_data()
        edit_sso_idp_form = SSOEnterpriseSettingsForm(self.idp, post_data)
        self.assertTrue(edit_sso_idp_form.is_valid())
        edit_sso_idp_form.update_identity_provider(self.accounting_admin)

        idp = IdentityProvider.objects.get(id=self.idp.id)
        self.assertTrue(idp.is_editable)
        self.assertFalse(idp.is_active)
        self.assertEqual(idp.last_modified_by, self.accounting_admin.username)
        self.assertNotEqual(idp.created_by, self.accounting_admin.username)
        self.assertEqual(idp.entity_id, post_data['entity_id'])
        self.assertEqual(idp.login_url, post_data['login_url'])
        self.assertEqual(idp.logout_url, post_data['logout_url'])
        self.assertIsNone(idp.idp_cert_public)
        self.assertIsNone(idp.date_idp_cert_expiration)

    def test_require_encrypted_assertions_is_saved(self):
        """
        Ensure that SSOEnterpriseSettingsForm updates the
        `require_encrypted_assertions property` on the IdentityProvider.
        """
        post_data = self._get_post_data(
            require_encrypted_assertions=True,
        )
        self.assertFalse(self.idp.require_encrypted_assertions)
        edit_sso_idp_form = SSOEnterpriseSettingsForm(self.idp, post_data)
        self.assertTrue(edit_sso_idp_form.is_valid())
        edit_sso_idp_form.update_identity_provider(self.accounting_admin)
        self.idp.refresh_from_db()
        self.assertTrue(self.idp.require_encrypted_assertions)
