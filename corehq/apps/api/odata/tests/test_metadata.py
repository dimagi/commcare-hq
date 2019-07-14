from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict

from django.test import TestCase
from django.urls import reverse

from flaky import flaky
from mock import patch

from corehq.apps.api.odata.tests.utils import (
    CaseOdataTestMixin,
    DeprecatedCaseOdataTestMixin,
    DeprecatedFormOdataTestMixin,
    FormOdataTestMixin,
    generate_api_key_from_web_user,
)
from corehq.apps.api.odata.views import (
    ODataCaseMetadataView,
    DeprecatedODataCaseMetadataView,
    DeprecatedODataFormMetadataView,
    ODataFormMetadataView,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.models import Domain
from corehq.apps.export.dbaccessors import get_odata_case_configs_by_domain, get_odata_form_configs_by_domain
from corehq.apps.export.models import CaseExportInstance, ExportColumn, FormExportInstance, TableConfiguration
from corehq.util.test_utils import flag_enabled

PATH_TO_TEST_DATA = ('..', '..', 'api', 'odata', 'tests', 'data')


class TestDeprecatedCaseMetadataDocument(TestCase, DeprecatedCaseOdataTestMixin, TestXmlMixin):

    view_urlname = DeprecatedODataCaseMetadataView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestDeprecatedCaseMetadataDocument, cls).setUpClass()
        cls._set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestDeprecatedCaseMetadataDocument, cls).tearDownClass()

    def test_no_credentials(self):
        with flag_enabled('ODATA'):
            response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        with flag_enabled('ODATA'):
            response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 401)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self.client.get(
                reverse(self.view_urlname, kwargs={'domain': other_domain.name}),
                HTTP_AUTHORIZATION='Basic ' + correct_credentials,
            )
        self.assertEqual(response.status_code, 403)

    def test_user_permissions(self):
        self.web_user.set_role(self.domain.name, 'none')
        self.web_user.save()
        self.addCleanup(self._setup_user_permissions)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_no_case_types(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch('corehq.apps.api.odata.views.get_case_type_to_properties', return_value={}):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('empty_metadata_document', override_path=PATH_TO_TEST_DATA)
        )

    def test_populated_metadata_document(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch(
                'corehq.apps.api.odata.views.get_case_type_to_properties',
                return_value=OrderedDict([
                    ('case_type_with_no_case_properties', []),
                    ('case_type_with_case_properties', ['property_1', 'property_2']),
                ])
            ):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('populated_case_metadata_document', override_path=PATH_TO_TEST_DATA)
        )


class TestDeprecatedCaseMetadataDocumentUsingApiKey(TestDeprecatedCaseMetadataDocument):

    @classmethod
    def setUpClass(cls):
        super(TestDeprecatedCaseMetadataDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestDeprecatedCaseMetadataDocumentUsingApiKey._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestDeprecatedCaseMetadataDocumentWithTwoFactorUsingApiKey(TestDeprecatedCaseMetadataDocumentUsingApiKey):
    pass


class TestDeprecatedFormMetadataDocument(TestCase, DeprecatedFormOdataTestMixin, TestXmlMixin):

    view_urlname = DeprecatedODataFormMetadataView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestDeprecatedFormMetadataDocument, cls).setUpClass()
        cls._set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestDeprecatedFormMetadataDocument, cls).tearDownClass()

    def test_no_credentials(self):
        with flag_enabled('ODATA'):
            response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 401)

    @flaky
    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        with flag_enabled('ODATA'):
            response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 401)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self.client.get(
                reverse(self.view_urlname, kwargs={'domain': other_domain.name, 'app_id': 'my_app_id'}),
                HTTP_AUTHORIZATION='Basic ' + correct_credentials,
            )
        self.assertEqual(response.status_code, 403)

    def test_user_permissions(self):
        self.web_user.set_role(self.domain.name, 'none')
        self.web_user.save()
        self.addCleanup(self._setup_user_permissions)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_no_xmlnss(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch('corehq.apps.api.odata.views.get_xmlns_to_properties', return_value={}):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('empty_metadata_document', override_path=PATH_TO_TEST_DATA)
        )

    def test_populated_metadata_document(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch(
                'corehq.apps.api.odata.views.get_xmlns_to_properties',
                return_value=OrderedDict([
                    ('form_with_no_properties', []),
                    ('form_with_properties', ['property_1', 'property_2']),
                ])
            ):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('populated_form_metadata_document', override_path=PATH_TO_TEST_DATA)
        )


class TestDeprecatedFormMetadataDocumentUsingApiKey(TestDeprecatedFormMetadataDocument):

    @classmethod
    def setUpClass(cls):
        super(TestDeprecatedFormMetadataDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestDeprecatedFormMetadataDocumentUsingApiKey._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestDeprecatedFormMetadataDocumentWithTwoFactorUsingApiKey(TestDeprecatedFormMetadataDocumentUsingApiKey):
    pass


class TestCaseMetadataDocument(TestCase, CaseOdataTestMixin, TestXmlMixin):

    view_urlname = ODataCaseMetadataView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestCaseMetadataDocument, cls).setUpClass()
        cls._set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestCaseMetadataDocument, cls).tearDownClass()

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
            reverse(self.view_urlname, kwargs={'domain': other_domain.name}),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 403)

    def test_user_permissions(self):
        self.web_user.set_role(self.domain.name, 'none')
        self.web_user.save()
        self.addCleanup(self._setup_user_permissions)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_successful_request(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertXmlEqual(
            self.get_xml('empty_metadata_document', override_path=PATH_TO_TEST_DATA),
            response.content
        )

    def test_populated_metadata_document(self):
        odata_config_1 = CaseExportInstance(
            _id='odata_config_1',
            domain=self.domain.name,
            is_odata_config=True,
            tables=[TableConfiguration(columns=[])]
        )
        odata_config_1.save()
        self.addCleanup(odata_config_1.delete)

        odata_config_2 = CaseExportInstance(
            _id='odata_config_2',
            domain=self.domain.name,
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    columns=[
                        ExportColumn(label='selected_property_1', selected=True),
                        ExportColumn(label='selected_property_2', selected=True),
                        ExportColumn(label='unselected_property'),
                    ],
                ),
            ]
        )
        odata_config_2.save()
        self.addCleanup(odata_config_2.delete)

        non_odata_config = CaseExportInstance(domain=self.domain.name)
        non_odata_config.save()
        self.addCleanup(non_odata_config.delete)

        config_in_other_domain = CaseExportInstance(domain='other_domain', is_odata_config=True)
        config_in_other_domain.save()
        self.addCleanup(config_in_other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch(
                'corehq.apps.api.odata.views.get_odata_case_configs_by_domain',
                return_value=sorted(
                    get_odata_case_configs_by_domain(self.domain.name),
                    key=lambda _config: _config.get_id
                )
            ):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertXmlEqual(
            self.get_xml(
                'populated_case_odata_metadata_document_from_config',
                override_path=PATH_TO_TEST_DATA
            ),
            response.content
        )


class TestCaseMetadataDocumentUsingApiKey(TestCaseMetadataDocument):

    @classmethod
    def setUpClass(cls):
        super(TestCaseMetadataDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestCaseMetadataDocument._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestCaseMetadataDocumentWithTwoFactorUsingApiKey(TestCaseMetadataDocumentUsingApiKey):
    pass


class TestFormMetadataDocument(TestCase, FormOdataTestMixin, TestXmlMixin):

    view_urlname = ODataFormMetadataView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestFormMetadataDocument, cls).setUpClass()
        cls._set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestFormMetadataDocument, cls).tearDownClass()

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
            reverse(self.view_urlname, kwargs={'domain': other_domain.name}),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 403)

    def test_user_permissions(self):
        self.web_user.set_role(self.domain.name, 'none')
        self.web_user.save()
        self.addCleanup(self._setup_user_permissions)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_successful_request(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertXmlEqual(
            self.get_xml('empty_metadata_document', override_path=PATH_TO_TEST_DATA),
            response.content
        )

    def test_populated_metadata_document(self):
        odata_config_1 = FormExportInstance(
            _id='odata_config_1',
            domain=self.domain.name,
            is_odata_config=True,
            tables=[TableConfiguration(columns=[])]
        )
        odata_config_1.save()
        self.addCleanup(odata_config_1.delete)

        odata_config_2 = FormExportInstance(
            _id='odata_config_2',
            domain=self.domain.name,
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    columns=[
                        ExportColumn(label='selected_property_1', selected=True),
                        ExportColumn(label='selected_property_2', selected=True),
                        ExportColumn(label='unselected_property'),
                    ],
                ),
            ]
        )
        odata_config_2.save()
        self.addCleanup(odata_config_2.delete)

        non_odata_config = FormExportInstance(domain=self.domain.name)
        non_odata_config.save()
        self.addCleanup(non_odata_config.delete)

        config_in_other_domain = FormExportInstance(domain='other_domain', is_odata_config=True)
        config_in_other_domain.save()
        self.addCleanup(config_in_other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch(
                'corehq.apps.api.odata.views.get_odata_form_configs_by_domain',
                return_value=sorted(
                    get_odata_form_configs_by_domain(self.domain.name),
                    key=lambda _config: _config.get_id
                )
            ):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertXmlEqual(
            self.get_xml(
                'populated_form_odata_metadata_document_from_config',
                override_path=PATH_TO_TEST_DATA
            ),
            response.content
        )


class TestFormMetadataDocumentUsingApiKey(TestFormMetadataDocument):

    @classmethod
    def setUpClass(cls):
        super(TestFormMetadataDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return cls._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestFormMetadataDocumentWithTwoFactorUsingApiKey(TestFormMetadataDocumentUsingApiKey):
    pass
