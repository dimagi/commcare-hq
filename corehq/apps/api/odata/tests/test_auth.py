from django.test import TestCase
from django.urls import reverse

from unittest import mock

from corehq.apps.domain.models import Domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.cases import case_adapter
from corehq.apps.export.models import CaseExportInstance, TableConfiguration
from corehq.util.test_utils import flag_enabled

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

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
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
        credentials = self._get_basic_credentials(self.web_user.username, self.api_key.key)
        response = self._execute_query(credentials)
        self.assertEqual(response.status_code, 200)

    def test_success_with_two_factor_api_key(self):
        with flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT'):
            self.test_success_with_api_key()
