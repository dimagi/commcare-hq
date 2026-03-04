from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from corehq.apps.domain.decorators import SSO_AUTH_FAIL_RESPONSE
from corehq.apps.domain.models import Domain
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.export.models import CaseExportInstance, TableConfiguration
from corehq.apps.sso.models import AuthenticatedEmailDomain, LoginEnforcementType
from corehq.apps.sso.tests import generator as sso_generator

from ..views import ODataCaseMetadataView
from .utils import (
    CaseOdataTestMixin,
    generate_api_key_from_web_user,
)


@es_test(requires=[case_adapter], setup_class=True)
@mock.patch('corehq.apps.api.odata.views.get_document_or_404', new=mock.MagicMock)
class TestOdataAuth(TestCase, CaseOdataTestMixin):

    view_urlname = ODataCaseMetadataView.urlname  # Testing auth only, any view will do

    @classmethod
    def setUpClass(cls):
        super(TestOdataAuth, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()
        cls.setup_sso_user()

    @classmethod
    def setup_sso_user(cls):
        cls.idp = sso_generator.create_idp('odata-sso-test', cls.account)
        cls.idp.is_active = True
        cls.idp.login_enforcement_type = LoginEnforcementType.GLOBAL
        cls.idp.save()
        cls.sso_email_domain = AuthenticatedEmailDomain.objects.create(
            email_domain='ssocompany.com',
            identity_provider=cls.idp,
        )
        cls.sso_user = cls.web_user.create(
            cls.domain.name, 'odata-sso-user@ssocompany.com', 'sso-password', None, None
        )
        cls.sso_user.set_role(cls.domain.name, 'admin')
        cls.sso_user.save()
        cls.addClassCleanup(cls.sso_user.delete, cls.domain.name, deleted_by=None)
        cls.addClassCleanup(cls.sso_email_domain.delete)
        cls.addClassCleanup(cls.idp.delete)

    @classmethod
    def tearDownClass(cls):
        cls._teardown_accounting()
        super(TestOdataAuth, cls).tearDownClass()

    def test_success(self):
        response = self._execute_query(self._get_correct_credentials())
        self.assertEqual(response.status_code, 200)

    def test_no_credentials(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 401)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        response = self.client.get(
            reverse(self.view_urlname, kwargs={
                'domain': other_domain.name,
                'config_id': 'my_config_id',
                'api_version': 'v1',
            }),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 403)

    def test_user_permissions(self):
        self.web_user.set_role(self.domain.name, 'none')
        self.web_user.save()
        self.addCleanup(self._setup_user_permissions)

        export_config = CaseExportInstance(
            _id='config_id',
            tables=[TableConfiguration(columns=[])],
            case_type='my_case_type',
            domain=self.domain.name,
        )
        export_config.save()
        self.addCleanup(export_config.delete)

        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 403)

    def test_success_with_api_key(self):
        self.api_key = generate_api_key_from_web_user(self.web_user)
        credentials = self._get_basic_credentials(self.web_user.username, self.api_key.plaintext_key)
        response = self._execute_query(credentials)
        self.assertEqual(response.status_code, 200)

    def test_sso_user_with_password_is_rejected(self):
        credentials = self._get_basic_credentials(self.sso_user.username, 'sso-password')
        response = self._execute_query(credentials)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), SSO_AUTH_FAIL_RESPONSE)

    def test_sso_user_with_api_key_in_basic_password_slot_succeeds(self):
        self.api_key = generate_api_key_from_web_user(self.sso_user)
        credentials = self._get_basic_credentials(self.sso_user.username, self.api_key.plaintext_key)
        response = self._execute_query(credentials)
        self.assertEqual(response.status_code, 200)

    @override_settings(REQUIRE_TWO_FACTOR_FOR_SUPERUSERS=True)
    def test_success_with_two_factor_api_key(self):
        self.web_user.is_superuser = True
        try:
            self.test_success_with_api_key()
        finally:
            self.web_user.is_superuser = False
