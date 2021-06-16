import uuid

from django.test.testcases import SimpleTestCase, TestCase

from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField
from corehq.apps.linked_domain.const import (
    MODEL_FLAGS,
    MODEL_LOCATION_DATA,
    MODEL_PREVIEWS,
    MODEL_PRODUCT_DATA,
    MODEL_ROLES,
    MODEL_USER_DATA,
)
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.view_helpers import (
    build_app_view_model,
    build_domain_level_view_models,
    build_feature_flag_view_models,
    build_fixture_view_model,
    build_keyword_view_model,
    build_report_view_model,
    get_apps,
    get_fixtures,
    get_keywords,
    get_reports,
)
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
    ReportMeta,
)
from corehq.util.test_utils import flag_enabled


def _create_report(domain, title="report", upstream_id=None, should_save=True, app_id=None):
    data_source = DataSourceConfiguration(
        domain=domain,
        table_id=uuid.uuid4().hex,
        referenced_doc_type='XFormInstance',
    )
    data_source.meta.build.app_id = app_id
    data_source.save()
    report = ReportConfiguration(
        domain=domain,
        config_id=data_source._id,
        title=title,
        report_meta=ReportMeta(created_by_builder=True, master_id=upstream_id),
    )
    if should_save:
        report.save()

    return report


def _create_keyword(domain, name="ping", upstream_id=None, should_save=True):
    keyword = Keyword(
        domain=domain,
        keyword=name,
        description="The description",
        override_open_sessions=True,
        upstream_id=upstream_id
    )
    if should_save:
        keyword.save()

    return keyword


def _create_fixture(domain, tag="table", should_save=True):
    data_type = FixtureDataType(
        domain=domain,
        tag=tag,
        fields=[
            FixtureTypeField(
                field_name="fixture_property",
                properties=["test"]
            )
        ],
        item_attributes=[],
        is_global=True
    )
    if should_save:
        data_type.save()

    return data_type


class TestGetDataModels(TestCase):
    file_path = ('data',)

    @classmethod
    def setUpClass(cls):
        super(TestGetDataModels, cls).setUpClass()
        cls.upstream_domain_obj = create_domain('upstream-domain')
        cls.upstream_domain = cls.upstream_domain_obj.name
        cls.downstream_domain_obj = create_domain('downstream-domain')
        cls.downstream_domain = cls.downstream_domain_obj.name

        cls.original_app = Application.new_app(cls.upstream_domain, "Original Application")
        cls.original_app.linked_whitelist = [cls.downstream_domain]
        cls.original_app.save()

        cls.linked_app = LinkedApplication.new_app(cls.downstream_domain, "Linked Application")
        cls.linked_app.upstream_app_id = cls.original_app._id
        cls.linked_app.save()

        cls.original_report = _create_report(cls.upstream_domain)
        cls.linked_report = _create_report(cls.downstream_domain, upstream_id=cls.original_report._id)

        cls.original_keyword = _create_keyword(cls.upstream_domain)
        cls.linked_keyword = _create_keyword(cls.downstream_domain, upstream_id=cls.original_keyword.id)

        cls.original_fixture = _create_fixture(cls.upstream_domain)

        cls.domain_link = DomainLink.link_domains(cls.downstream_domain, cls.upstream_domain)

    @classmethod
    def tearDownClass(cls):
        delete_all_report_configs()
        cls.original_fixture.delete()
        cls.original_keyword.delete()
        cls.linked_keyword.delete()
        cls.original_report.delete()
        cls.linked_report.delete()
        cls.linked_app.delete()
        cls.original_app.delete()
        cls.domain_link.delete()
        cls.upstream_domain_obj.delete()
        cls.downstream_domain_obj.delete()
        super(TestGetDataModels, cls).tearDownClass()

    def test_get_apps_for_upstream_domain(self):
        expected_upstream_app_names = [self.original_app._id]
        expected_downstream_app_names = []

        upstream_apps, downstream_apps = get_apps(self.upstream_domain)
        actual_upstream_app_names = [app._id for app in upstream_apps.values()]
        actual_downstream_app_names = [app._id for app in downstream_apps.values()]

        self.assertEqual(expected_upstream_app_names, actual_upstream_app_names)
        self.assertEqual(expected_downstream_app_names, actual_downstream_app_names)

    def test_get_apps_for_downstream_domain(self):
        expected_original_app_names = []
        expected_linked_app_names = [self.linked_app._id]

        original_apps, linked_apps = get_apps(self.downstream_domain)
        actual_original_app_names = [app._id for app in original_apps.values()]
        actual_linked_app_names = [app._id for app in linked_apps.values()]

        self.assertEqual(expected_original_app_names, actual_original_app_names)
        self.assertEqual(expected_linked_app_names, actual_linked_app_names)

    def test_get_reports_for_upstream_domain(self):
        expected_original_reports = [self.original_report._id]
        expected_linked_reports = []

        original_reports, linked_reports = get_reports(self.upstream_domain)
        actual_original_reports = [report._id for report in original_reports.values()]
        actual_linked_reports = [report._id for report in linked_reports.values()]

        self.assertEqual(expected_original_reports, actual_original_reports)
        self.assertEqual(expected_linked_reports, actual_linked_reports)

    def test_get_reports_for_downstream_domain(self):
        expected_original_reports = []
        expected_linked_reports = [self.linked_report._id]

        original_reports, linked_reports = get_reports(self.downstream_domain)
        actual_original_reports = [report._id for report in original_reports.values()]
        actual_linked_reports = [report._id for report in linked_reports.values()]

        self.assertEqual(expected_original_reports, actual_original_reports)
        self.assertEqual(expected_linked_reports, actual_linked_reports)

    def test_get_keywords_for_upstream_domain(self):
        expected_original_keywords = [str(self.original_keyword.id)]
        expected_linked_keywords = []

        original_keywords, linked_keywords = get_keywords(self.upstream_domain)
        actual_original_keywords = [str(keyword.id) for keyword in original_keywords.values()]
        actual_linked_keywords = [str(keyword.id) for keyword in linked_keywords.values()]

        self.assertEqual(expected_original_keywords, actual_original_keywords)
        self.assertEqual(expected_linked_keywords, actual_linked_keywords)

    def test_get_keywords_for_downstream_domain(self):
        expected_original_keywords = []
        expected_linked_keywords = [str(self.linked_keyword.id)]

        original_keywords, linked_keywords = get_keywords(self.downstream_domain)
        actual_original_keywords = [str(keyword.id) for keyword in original_keywords.values()]
        actual_linked_keywords = [str(keyword.id) for keyword in linked_keywords.values()]

        self.assertEqual(expected_original_keywords, actual_original_keywords)
        self.assertEqual(expected_linked_keywords, actual_linked_keywords)

    def test_get_fixtures_for_upstream_domain(self):
        expected_original_fixtures = [self.original_fixture._id]
        expected_linked_fixtures = []

        original_fixtures, linked_fixtures = get_fixtures(self.upstream_domain, None)
        actual_original_fixtures = [fixture._id for fixture in original_fixtures.values()]
        actual_linked_fixtures = [fixture._id for fixture in linked_fixtures.values()]

        self.assertEqual(expected_original_fixtures, actual_original_fixtures)
        self.assertEqual(expected_linked_fixtures, actual_linked_fixtures)

    def test_get_fixtures_for_downstream_domain(self):
        expected_original_fixtures = []
        expected_linked_fixtures = [self.original_fixture._id]

        original_fixtures, linked_fixtures = get_fixtures(self.downstream_domain, self.domain_link)
        actual_original_fixtures = [fixture._id for fixture in original_fixtures.values()]
        actual_linked_fixtures = [fixture._id for fixture in linked_fixtures.values()]

        self.assertEqual(expected_original_fixtures, actual_original_fixtures)
        self.assertEqual(expected_linked_fixtures, actual_linked_fixtures)


class TestBuildIndividualViewModels(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestBuildIndividualViewModels, cls).setUpClass()
        cls.domain_obj = create_domain('test-create-view-model-domain')
        cls.domain = cls.domain_obj.name

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestBuildIndividualViewModels, cls).tearDownClass()

    def test_build_app_view_model_returns_match(self):
        app = Application.new_app(self.domain, "Test Application")
        # set _id rather than actually saving the object
        app._id = 'abc123'

        expected_view_model = {
            'type': 'app',
            'name': 'Application (Test Application)',
            'detail': {'app_id': 'abc123'},
            'last_update': None,
            'can_update': True
        }

        actual_view_model = build_app_view_model(app)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_app_view_model_with_none_returns_unknown(self):
        app = None
        expected_view_model = {
            'type': 'app',
            'name': 'Application (Unknown App)',
            'detail': None,
            'last_update': None,
            'can_update': False
        }

        actual_view_model = build_app_view_model(app)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_app_view_model_with_empty_dict_returns_unknown(self):
        app = {}
        expected_view_model = {
            'type': 'app',
            'name': 'Application (Unknown App)',
            'detail': None,
            'last_update': None,
            'can_update': False
        }

        actual_view_model = build_app_view_model(app)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_fixture_view_model_returns_match(self):
        fixture = _create_fixture(self.domain, tag="test-table", should_save=False)
        expected_view_model = {
            'type': 'fixture',
            'name': 'Lookup Table (test-table)',
            'detail': {'tag': 'test-table'},
            'last_update': None,
            'can_update': True
        }

        actual_view_model = build_fixture_view_model(fixture)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_fixture_view_model_with_none_returns_unknown(self):
        fixture = None
        expected_view_model = {
            'type': 'fixture',
            'name': 'Lookup Table (Unknown Table)',
            'detail': None,
            'last_update': None,
            'can_update': False
        }

        actual_view_model = build_fixture_view_model(fixture)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_fixture_view_model_with_empty_returns_none(self):
        fixture = {}
        expected_view_model = {
            'type': 'fixture',
            'name': 'Lookup Table (Unknown Table)',
            'detail': None,
            'last_update': None,
            'can_update': False
        }

        actual_view_model = build_fixture_view_model(fixture)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_report_view_model(self):
        report = _create_report(self.domain, title='report-test', should_save=False)
        report._id = 'abc123'
        expected_view_model = {
            'type': 'report',
            'name': 'Report (report-test)',
            'detail': {'report_id': 'abc123'},
            'last_update': None,
            'can_update': True
        }

        actual_view_model = build_report_view_model(report)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_report_view_model_with_none_returns_unknown(self):
        report = None
        expected_view_model = {
            'type': 'report',
            'name': 'Report (Unknown Report)',
            'detail': None,
            'last_update': None,
            'can_update': False
        }

        actual_view_model = build_report_view_model(report)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_report_view_model_with_empty_returns_unknown(self):
        report = {}
        expected_view_model = {
            'type': 'report',
            'name': 'Report (Unknown Report)',
            'detail': None,
            'last_update': None,
            'can_update': False
        }

        actual_view_model = build_report_view_model(report)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_keyword_view_model_returns_match(self):
        keyword = _create_keyword(self.domain, name='keyword-test', should_save=False)
        keyword.id = '100'

        expected_view_model = {
            'type': 'keyword',
            'name': 'Keyword (keyword-test)',
            'detail': {'keyword_id': '100'},
            'last_update': None,
            'can_update': True
        }

        actual_view_model = build_keyword_view_model(keyword)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_keyword_view_model_with_none_returns_unknown(self):
        keyword = None
        expected_view_model = {
            'type': 'keyword',
            'name': 'Keyword (Deleted Keyword)',
            'detail': None,
            'last_update': None,
            'can_update': False
        }

        actual_view_model = build_keyword_view_model(keyword)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_keyword_view_model_with_empty_returns_unknown(self):
        keyword = {}
        expected_view_model = {
            'type': 'keyword',
            'name': 'Keyword (Deleted Keyword)',
            'detail': None,
            'last_update': None,
            'can_update': False
        }

        actual_view_model = build_keyword_view_model(keyword)
        self.assertEqual(expected_view_model, actual_view_model)


class TestBuildFeatureFlagViewModels(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestBuildFeatureFlagViewModels, cls).setUpClass()
        cls.domain_obj = create_domain('test-build-ff-view-models')
        cls.domain = cls.domain_obj.name

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestBuildFeatureFlagViewModels, cls).tearDownClass()

    def test_build_feature_flag_view_models_returns_empty(self):
        expected_view_models = []

        view_models = build_feature_flag_view_models(self.domain)

        self.assertEqual(expected_view_models, view_models)

    @flag_enabled('SYNC_SEARCH_CASE_CLAIM')
    def test_build_feature_flag_view_models_returns_case_search(self):
        expected_view_models = [
            {
                'type': 'case_search_data',
                'name': 'Case Search Settings',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            }
        ]
        view_models = build_feature_flag_view_models(self.domain)

        self.assertEqual(expected_view_models, view_models)

    @flag_enabled('DATA_DICTIONARY')
    def test_build_feature_flag_view_models_returns_data_dictionary(self):
        expected_view_models = [
            {
                'type': 'data_dictionary',
                'name': 'Data Dictionary',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            }
        ]
        view_models = build_feature_flag_view_models(self.domain)

        self.assertEqual(expected_view_models, view_models)

    @flag_enabled('WIDGET_DIALER')
    def test_build_feature_flag_view_models_returns_dialer_settings(self):
        expected_view_models = [
            {
                'type': 'dialer_settings',
                'name': 'Dialer Settings',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            }
        ]
        view_models = build_feature_flag_view_models(self.domain)

        self.assertEqual(expected_view_models, view_models)

    @flag_enabled('GAEN_OTP_SERVER')
    def test_build_feature_flag_view_models_returns_otp_settings(self):
        expected_view_models = [
            {
                'type': 'otp_settings',
                'name': 'OTP Pass-through Settings',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            }
        ]
        view_models = build_feature_flag_view_models(self.domain)

        self.assertEqual(expected_view_models, view_models)

    @flag_enabled('HMAC_CALLOUT')
    def test_build_feature_flag_view_models_returns_hmac_callout(self):
        expected_view_models = [
            {
                'type': 'hmac_callout_settings',
                'name': 'Signed Callout',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            }
        ]
        view_models = build_feature_flag_view_models(self.domain)

        self.assertEqual(expected_view_models, view_models)


class TestBuildDomainLevelViewModels(SimpleTestCase):

    def test_build_domain_level_view_models_returns_all(self):
        expected_view_models = [
            {
                'type': 'custom_user_data',
                'name': 'Custom User Data Fields',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            },
            {
                'type': 'custom_product_data',
                'name': 'Custom Product Data Fields',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            },
            {
                'type': 'custom_location_data',
                'name': 'Custom Location Data Fields',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            },
            {
                'type': 'roles',
                'name': 'User Roles',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            },
            {
                'type': 'toggles',
                'name': 'Feature Flags',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            },
            {
                'type': 'previews',
                'name': 'Feature Previews',
                'detail': None,
                'last_update': 'Never',
                'can_update': True
            },
        ]

        view_models = build_domain_level_view_models()
        self.assertEqual(expected_view_models, view_models)

    def test_build_domain_level_view_models_ignores_models(self):
        expected_view_models = []
        ignore_models = [MODEL_USER_DATA, MODEL_PRODUCT_DATA, MODEL_LOCATION_DATA, MODEL_ROLES, MODEL_FLAGS,
                         MODEL_PREVIEWS]

        view_models = build_domain_level_view_models(ignore_models=ignore_models)

        self.assertEqual(expected_view_models, view_models)
