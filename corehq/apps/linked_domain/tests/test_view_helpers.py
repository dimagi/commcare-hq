import uuid
from datetime import datetime

from django.test.testcases import SimpleTestCase, TestCase

import pytz

from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.fixtures.models import LookupTable, TypeField
from corehq.apps.linked_domain.const import (
    DOMAIN_LEVEL_DATA_MODELS,
    FEATURE_FLAG_DATA_MODELS,
    MODEL_APP,
    MODEL_AUTO_UPDATE_RULE,
    MODEL_FIXTURE,
    MODEL_FLAGS,
    MODEL_KEYWORD,
    MODEL_REPORT,
    SUPERUSER_DATA_MODELS,
)
from corehq.apps.linked_domain.models import (
    AppLinkDetail,
    DomainLink,
    DomainLinkHistory,
    FixtureLinkDetail,
    KeywordLinkDetail,
    ReportLinkDetail,
    UpdateRuleLinkDetail,
)
from corehq.apps.linked_domain.view_helpers import (
    build_app_view_model,
    build_domain_level_view_models,
    build_feature_flag_view_models,
    build_fixture_view_model,
    build_keyword_view_model,
    build_pullable_view_models_from_data_models,
    build_report_view_model,
    build_superuser_view_models,
    build_ucr_expression_view_model,
    build_view_models_from_data_models,
    get_upstream_and_downstream_apps,
    get_upstream_and_downstream_fixtures,
    get_upstream_and_downstream_keywords,
    get_upstream_and_downstream_reports,
    get_upstream_and_downstream_update_rules,
    get_upstream_and_downstream_ucr_expressions,
    pop_app,
    pop_fixture,
    pop_keyword,
    pop_report,
    pop_ucr_expression,
)
from corehq.apps.sms.models import Keyword, KeywordAction
from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
    ReportMeta,
    UCRExpression,
)
from corehq import privileges
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.util.test_utils import (
    flag_enabled,
    privilege_enabled,
)


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


def _create_keyword(domain, name="ping", upstream_id=None, should_save=True, is_grouped=False):
    keyword = Keyword(
        domain=domain,
        keyword=name,
        description="The description",
        override_open_sessions=True,
        upstream_id=upstream_id
    )

    if should_save:
        keyword.save()

    if is_grouped:
        keyword.keywordaction_set.create(
            recipient=KeywordAction.RECIPIENT_USER_GROUP,
            recipient_id='abc123',
            action=KeywordAction.ACTION_SMS,
            message_content='Test',
        )

    return keyword


def _create_ucr_expression(domain, name="ping", upstream_id=None, should_save=True,):
    ucr_expression = UCRExpression(
        domain=domain,
        name=name,
        description="The description",
        expression_type=UCR_NAMED_EXPRESSION,
        definition={"type": "constant", "constant": "Constant repetition carries conviction."},
        upstream_id=upstream_id,
    )

    if should_save:
        ucr_expression.save()

    return ucr_expression


def _create_fixture(domain, tag="table", should_save=True):
    data_type = LookupTable(
        domain=domain,
        tag=tag,
        fields=[
            TypeField(
                name="fixture_property",
                properties=["test"]
            )
        ],
        item_attributes=[],
        is_global=True
    )
    if should_save:
        data_type.save()

    return data_type


def _create_update_rule(domain, name="update_rule", workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
                        should_save=True):
    rule = AutomaticUpdateRule(
        domain=domain,
        name=name,
        case_type='test',
        active=True,
        workflow=workflow
    )

    if should_save:
        rule.save()

    return rule


class BaseLinkedDomainTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseLinkedDomainTest, cls).setUpClass()
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

        cls.original_ucr_expression = _create_ucr_expression(cls.upstream_domain)
        cls.linked_ucr_expression = _create_ucr_expression(
            cls.downstream_domain, upstream_id=cls.original_ucr_expression.id
        )

        cls.original_fixture = _create_fixture(cls.upstream_domain)
        # Couch lookup tables are cleaned up by domain deletion

        cls.domain_link = DomainLink.link_domains(cls.downstream_domain, cls.upstream_domain)

    @classmethod
    def tearDownClass(cls):
        delete_all_report_configs()
        cls.original_keyword.delete()
        cls.linked_keyword.delete()
        cls.original_report.delete()
        cls.linked_report.delete()
        cls.linked_app.delete()
        cls.original_app.delete()
        cls.domain_link.delete()
        cls.upstream_domain_obj.delete()
        cls.downstream_domain_obj.delete()
        super(BaseLinkedDomainTest, cls).tearDownClass()


class TestGetDataModels(BaseLinkedDomainTest):

    def test_get_apps_for_upstream_domain(self):
        expected_upstream_app_names = [self.original_app._id]
        expected_downstream_app_names = []

        upstream_apps, downstream_apps = get_upstream_and_downstream_apps(self.upstream_domain)
        actual_upstream_app_names = [app._id for app in upstream_apps.values()]
        actual_downstream_app_names = [app._id for app in downstream_apps.values()]

        self.assertEqual(expected_upstream_app_names, actual_upstream_app_names)
        self.assertEqual(expected_downstream_app_names, actual_downstream_app_names)

    def test_get_apps_for_downstream_domain(self):
        expected_upstream_app_names = []
        expected_downstream_app_names = [self.linked_app._id]

        upstream_apps, downstream_apps = get_upstream_and_downstream_apps(self.downstream_domain)
        actual_upstream_app_names = [app._id for app in upstream_apps.values()]
        actual_downstream_app_names = [app._id for app in downstream_apps.values()]

        self.assertEqual(expected_upstream_app_names, actual_upstream_app_names)
        self.assertEqual(expected_downstream_app_names, actual_downstream_app_names)

    def test_get_reports_for_upstream_domain(self):
        expected_upstream_reports = [self.original_report._id]
        expected_downstream_reports = []

        upstream_reports, downstream_reports = get_upstream_and_downstream_reports(self.upstream_domain)
        actual_upstream_reports = [report._id for report in upstream_reports.values()]
        actual_downstream_reports = [report._id for report in downstream_reports.values()]

        self.assertEqual(expected_upstream_reports, actual_upstream_reports)
        self.assertEqual(expected_downstream_reports, actual_downstream_reports)

    def test_get_reports_for_downstream_domain(self):
        expected_upstream_reports = []
        expected_downstream_reports = [self.linked_report._id]

        upstream_reports, downstream_reports = get_upstream_and_downstream_reports(self.downstream_domain)
        actual_upstream_reports = [report._id for report in upstream_reports.values()]
        actual_downstream_reports = [report._id for report in downstream_reports.values()]

        self.assertEqual(expected_upstream_reports, actual_upstream_reports)
        self.assertEqual(expected_downstream_reports, actual_downstream_reports)

    def test_get_keywords_for_upstream_domain(self):
        expected_upstream_keywords = [str(self.original_keyword.id)]
        expected_downstream_keywords = []

        upstream_keywords, downstream_keywords = get_upstream_and_downstream_keywords(self.upstream_domain)
        actual_upstream_keywords = [str(keyword.id) for keyword in upstream_keywords.values()]
        actual_downstream_keywords = [str(keyword.id) for keyword in downstream_keywords.values()]

        self.assertEqual(expected_upstream_keywords, actual_upstream_keywords)
        self.assertEqual(expected_downstream_keywords, actual_downstream_keywords)

    def test_get_keywords_for_downstream_domain(self):
        expected_upstream_keywords = []
        expected_downstream_keywords = [str(self.linked_keyword.id)]

        upstream_keywords, downstream_keywords = get_upstream_and_downstream_keywords(self.downstream_domain)
        actual_upstream_keywords = [str(keyword.id) for keyword in upstream_keywords.values()]
        actual_downstream_keywords = [str(keyword.id) for keyword in downstream_keywords.values()]

        self.assertEqual(expected_upstream_keywords, actual_upstream_keywords)
        self.assertEqual(expected_downstream_keywords, actual_downstream_keywords)

    def test_get_ucr_expressions_for_upstream_domain(self):
        expected_upstream_ucr_expressions = [str(self.original_ucr_expression.id)]
        expected_downstream_ucr_expressions = []

        upstream_ucr_expressions, downstream_ucr_expressions = get_upstream_and_downstream_ucr_expressions(
            self.upstream_domain
        )
        actual_upstream_ucr_expressions = [
            str(ucr_expression.id) for ucr_expression in upstream_ucr_expressions.values()
        ]
        actual_downstream_ucr_expressions = [
            str(ucr_expression.id) for ucr_expression in downstream_ucr_expressions.values()
        ]

        self.assertEqual(expected_upstream_ucr_expressions, actual_upstream_ucr_expressions)
        self.assertEqual(expected_downstream_ucr_expressions, actual_downstream_ucr_expressions)

    def test_get_ucr_expressions_for_downstream_domain(self):
        expected_upstream_ucr_expressions = []
        expected_downstream_ucr_expressions = [str(self.linked_ucr_expression.id)]

        upstream_ucr_expressions, downstream_ucr_expressions = get_upstream_and_downstream_ucr_expressions(
            self.downstream_domain
        )
        actual_upstream_ucr_expressions = [
            str(ucr_expression.id) for ucr_expression in upstream_ucr_expressions.values()
        ]
        actual_downstream_ucr_expressions = [
            str(ucr_expression.id) for ucr_expression in downstream_ucr_expressions.values()
        ]

        self.assertEqual(expected_upstream_ucr_expressions, actual_upstream_ucr_expressions)
        self.assertEqual(expected_downstream_ucr_expressions, actual_downstream_ucr_expressions)

    def test_get_fixtures_for_upstream_domain(self):
        expected_upstream_fixtures = [self.original_fixture.id]
        expected_downstream_fixtures = []

        upstream_fixtures, downstream_fixtures = get_upstream_and_downstream_fixtures(self.upstream_domain, None)
        actual_upstream_fixtures = [fixture.id for fixture in upstream_fixtures.values()]
        actual_downstream_fixtures = [fixture.id for fixture in downstream_fixtures.values()]

        self.assertEqual(expected_upstream_fixtures, actual_upstream_fixtures)
        self.assertEqual(expected_downstream_fixtures, actual_downstream_fixtures)

    def test_get_fixtures_for_downstream_domain(self):
        expected_upstream_fixtures = []
        expected_downstream_fixtures = [self.original_fixture.id]

        upstream_fixtures, downstream_fixtures = get_upstream_and_downstream_fixtures(
            self.downstream_domain, self.domain_link
        )
        actual_upstream_fixtures = [fixture.id for fixture in upstream_fixtures.values()]
        actual_downstream_fixtures = [fixture.id for fixture in downstream_fixtures.values()]

        self.assertEqual(expected_upstream_fixtures, actual_upstream_fixtures)
        self.assertEqual(expected_downstream_fixtures, actual_downstream_fixtures)


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
            'can_update': True,
            'is_linkable': True,
        }

        actual_view_model = build_app_view_model(app)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_app_view_model_with_none_returns_none(self):
        app = None
        actual_view_model = build_app_view_model(app)
        self.assertIsNone(actual_view_model)

    def test_build_app_view_model_with_empty_dict_returns_none(self):
        app = {}
        actual_view_model = build_app_view_model(app)
        self.assertIsNone(actual_view_model)

    def test_build_fixture_view_model_returns_match(self):
        fixture = _create_fixture(self.domain, tag="test-table", should_save=False)
        expected_view_model = {
            'type': 'fixture',
            'name': 'Lookup Table (test-table)',
            'detail': {'tag': 'test-table'},
            'last_update': None,
            'can_update': True,
            'is_linkable': True,
        }
        actual_view_model = build_fixture_view_model(fixture)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_fixture_view_model_with_none_returns_none(self):
        fixture = None
        actual_view_model = build_fixture_view_model(fixture)
        self.assertIsNone(actual_view_model)

    def test_build_fixture_view_model_with_empty_returns_none(self):
        fixture = {}
        actual_view_model = build_fixture_view_model(fixture)
        self.assertIsNone(actual_view_model)

    def test_build_report_view_model(self):
        report = _create_report(self.domain, title='report-test', should_save=False)
        report._id = 'abc123'
        expected_view_model = {
            'type': 'report',
            'name': 'Report (report-test)',
            'detail': {'report_id': 'abc123'},
            'last_update': None,
            'can_update': True,
            'is_linkable': True,
        }

        actual_view_model = build_report_view_model(report)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_report_view_model_with_none_returns_none(self):
        report = None
        actual_view_model = build_report_view_model(report)
        self.assertIsNone(actual_view_model)

    def test_build_report_view_model_with_empty_returns_none(self):
        report = {}
        actual_view_model = build_report_view_model(report)
        self.assertIsNone(actual_view_model)

    def test_build_keyword_view_model_returns_match(self):
        keyword = _create_keyword(self.domain, name='keyword-test', should_save=False)
        keyword.id = '100'

        expected_view_model = {
            'type': 'keyword',
            'name': 'Keyword (keyword-test)',
            'detail': {'keyword_id': '100'},
            'last_update': None,
            'can_update': True,
            'is_linkable': True,
        }

        actual_view_model = build_keyword_view_model(keyword)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_keyword_view_model_with_none_returns_none(self):
        keyword = None
        actual_view_model = build_keyword_view_model(keyword)
        self.assertIsNone(actual_view_model)

    def test_build_keyword_view_model_with_empty_returns_none(self):
        keyword = {}
        actual_view_model = build_keyword_view_model(keyword)
        self.assertIsNone(actual_view_model)

    def test_build_keyword_view_model_with_grouped_returns_unlinkable(self):
        keyword = _create_keyword(self.domain, name='keyword-test', is_grouped=True)
        expected_view_model = {
            'type': 'keyword',
            'name': 'Keyword (keyword-test)',
            'detail': {'keyword_id': f'{keyword.id}'},
            'last_update': None,
            'can_update': True,
            'is_linkable': False,
        }

        actual_view_model = build_keyword_view_model(keyword)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_ucr_expression_view_model_returns_match(self):
        ucr_expression = _create_ucr_expression(self.domain, should_save=False)
        ucr_expression.id = '100'

        expected_view_model = {
            'type': 'ucr_expression',
            'name': f'Data Expressions and Filters ({ucr_expression.name})',
            'detail': {'ucr_expression_id': '100'},
            'last_update': None,
            'can_update': True,
            'is_linkable': True,
        }

        actual_view_model = build_ucr_expression_view_model(ucr_expression)
        self.assertEqual(expected_view_model, actual_view_model)

    def test_build_ucr_expression_view_model_with_none_returns_none(self):
        ucr_expression = None
        actual_view_model = build_ucr_expression_view_model(ucr_expression)
        self.assertIsNone(actual_view_model)

    def test_build_ucr_expression_view_model_with_empty_returns_none(self):
        ucr_expression = {}
        actual_view_model = build_ucr_expression_view_model(ucr_expression)
        self.assertIsNone(actual_view_model)


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
                'can_update': True,
                'is_linkable': True,
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
                'can_update': True,
                'is_linkable': True,
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
                'can_update': True,
                'is_linkable': True,
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
                'can_update': True,
                'is_linkable': True,
            }
        ]
        view_models = build_feature_flag_view_models(self.domain)

        self.assertEqual(expected_view_models, view_models)

    @flag_enabled('COMMTRACK')
    def test_build_feature_flag_view_models_returns_product_data_fields(self):
        expected_view_models = [
            {
                'type': 'custom_product_data',
                'name': 'Custom Product Data Fields',
                'detail': None,
                'last_update': 'Never',
                'can_update': True,
                'is_linkable': True,
            }
        ]
        view_models = build_feature_flag_view_models(self.domain)

        self.assertEqual(expected_view_models, view_models)

    @flag_enabled('EMBEDDED_TABLEAU')
    def test_build_feature_flag_view_models_returns_tableau_server_and_visualizations(self):
        expected_view_models = [
            {
                'type': 'tableau_server_and_visualizations',
                'name': 'Tableau Server and Visualizations',
                'detail': None,
                'last_update': 'Never',
                'can_update': True,
                'is_linkable': True,
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
                'can_update': True,
                'is_linkable': True,
            },
            {
                'type': 'custom_location_data',
                'name': 'Custom Location Data Fields',
                'detail': None,
                'last_update': 'Never',
                'can_update': True,
                'is_linkable': True,
            },
            {
                'type': 'roles',
                'name': 'User Roles',
                'detail': None,
                'last_update': 'Never',
                'can_update': True,
                'is_linkable': True,
            },
            {
                'type': 'previews',
                'name': 'Feature Previews',
                'detail': None,
                'last_update': 'Never',
                'can_update': True,
                'is_linkable': True,
            },
            {
                'type': 'auto_update_rules',
                'name': 'Automatic Update Rules',
                'detail': None,
                'last_update': 'Never',
                'can_update': True,
                'is_linkable': True,
            },
            {
                'type': 'data_dictionary',
                'name': 'Data Dictionary',
                'detail': None,
                'last_update': 'Never',
                'can_update': True,
                'is_linkable': True,
            },
        ]

        view_models = build_domain_level_view_models()
        self.assertEqual(expected_view_models, view_models)

    def test_build_domain_level_view_models_ignores_models(self):
        expected_view_models = []
        ignore_models = dict(DOMAIN_LEVEL_DATA_MODELS).keys()

        view_models = build_domain_level_view_models(ignore_models=ignore_models)

        self.assertEqual(expected_view_models, view_models)


class TestBuildSuperuserViewModels(SimpleTestCase):

    def test_build_superuser_view_models_returns_all(self):
        expected_view_models = [
            {
                'type': 'toggles',
                'name': 'Feature Flags',
                'detail': None,
                'last_update': 'Never',
                'can_update': True,
                'is_linkable': True,
            },
        ]

        view_models = build_superuser_view_models()
        self.assertEqual(expected_view_models, view_models)

    def test_build_superuser_view_models_ignores_models(self):
        expected_view_models = []
        ignore_models = dict(SUPERUSER_DATA_MODELS).keys()

        view_models = build_superuser_view_models(ignore_models=ignore_models)

        self.assertEqual(expected_view_models, view_models)


class TestBuildViewModelsFromDataModels(BaseLinkedDomainTest):
    """
    Testing for length of view models below is sufficient because the content is tested in a lower level test
    See TestBuildIndividualViewModels, TestBuildFeatureFlagViewModels, TestBuildDomainLevelViewModels,
    TestBuildSuperuserViewModels
    """

    def test_domain_level_view_models_are_built(self):
        view_models = build_view_models_from_data_models(self.downstream_domain, {}, {}, {}, {}, {}, {})
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS)
        self.assertEqual(expected_length, len(view_models))

    def test_domain_level_view_models_are_ignored(self):
        view_models = build_view_models_from_data_models(
            self.downstream_domain, {}, {}, {}, {}, {}, {}, ignore_models=dict(DOMAIN_LEVEL_DATA_MODELS).keys()
        )
        self.assertEqual(0, len(view_models))

    @privilege_enabled(privileges.DATA_DICTIONARY)
    @flag_enabled('SYNC_SEARCH_CASE_CLAIM')
    @flag_enabled('WIDGET_DIALER')
    @flag_enabled('GAEN_OTP_SERVER')
    @flag_enabled('HMAC_CALLOUT')
    @flag_enabled('EMBEDDED_TABLEAU')
    @flag_enabled('COMMTRACK')
    def test_feature_flag_view_models_are_built(self):
        view_models = build_view_models_from_data_models(self.downstream_domain, {}, {}, {}, {}, {}, {})
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + len(FEATURE_FLAG_DATA_MODELS)
        self.assertEqual(expected_length, len(view_models))

    @privilege_enabled(privileges.DATA_DICTIONARY)
    @flag_enabled('SYNC_SEARCH_CASE_CLAIM')
    @flag_enabled('WIDGET_DIALER')
    @flag_enabled('GAEN_OTP_SERVER')
    @flag_enabled('HMAC_CALLOUT')
    @flag_enabled('EMBEDDED_TABLEAU')
    @flag_enabled('COMMTRACK')
    def test_feature_flag_view_models_are_ignored(self):
        view_models = build_view_models_from_data_models(
            self.downstream_domain, {}, {}, {}, {}, {}, {}, ignore_models=dict(FEATURE_FLAG_DATA_MODELS).keys()
        )
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS)
        self.assertEqual(expected_length, len(view_models))

    def test_superuser_view_models_are_built_if_superuser(self):
        view_models = build_view_models_from_data_models(
            self.downstream_domain, {}, {}, {}, {}, {}, {}, is_superuser=True
        )
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + len(SUPERUSER_DATA_MODELS)
        self.assertEqual(expected_length, len(view_models))

    def test_superuser_view_models_are_not_built_if_not_superuser(self):
        # same as test_domain_level_view_models_are_built, but added to be explicit
        view_models = build_view_models_from_data_models(
            self.downstream_domain, {}, {}, {}, {}, {}, {}, is_superuser=False
        )
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS)
        self.assertEqual(expected_length, len(view_models))

    def test_superuser_view_models_are_ignored(self):
        view_models = build_view_models_from_data_models(self.downstream_domain, {}, {}, {}, {}, {}, {},
                                                         ignore_models=dict(SUPERUSER_DATA_MODELS).keys(),
                                                         is_superuser=True)
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS)
        self.assertEqual(expected_length, len(view_models))

    def test_app_view_models_are_built(self):
        _, downstream_apps = get_upstream_and_downstream_apps(self.downstream_domain)
        view_models = build_view_models_from_data_models(self.downstream_domain, downstream_apps,
                                                         {}, {}, {}, {}, {})
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def test_fixture_view_models_are_built(self):
        _, downstream_fixtures = get_upstream_and_downstream_fixtures(self.downstream_domain, self.domain_link)
        view_models = build_view_models_from_data_models(
            self.downstream_domain, {}, downstream_fixtures, {}, {}, {}, {}
        )
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def test_report_view_models_are_built(self):
        _, downstream_reports = get_upstream_and_downstream_reports(self.downstream_domain)
        view_models = build_view_models_from_data_models(
            self.downstream_domain, {}, {}, downstream_reports, {}, {}, {}
        )
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def test_keyword_view_models_are_built(self):
        _, downstream_keywords = get_upstream_and_downstream_keywords(self.downstream_domain)
        view_models = build_view_models_from_data_models(
            self.downstream_domain, {}, {}, {}, downstream_keywords, {}, {}
        )
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def test_ucr_expression_view_models_are_built(self):
        _, downstream_ucr_expressions = get_upstream_and_downstream_ucr_expressions(self.downstream_domain)
        view_models = build_view_models_from_data_models(
            self.downstream_domain, {}, {}, {}, {}, downstream_ucr_expressions, {}
        )
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def test_update_rule_view_models_are_built(self):
        _create_update_rule(self.upstream_domain, workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)

        upstream_rules, _ = get_upstream_and_downstream_update_rules(self.upstream_domain, self.domain_link)

        view_models = build_view_models_from_data_models(
            self.upstream_domain, {}, {}, {}, {}, {}, upstream_rules
        )

        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))


class TestBuildPullableViewModels(BaseLinkedDomainTest):
    """
    This method relies on build_view_models_from_data_models which is already tested
    This aims to test scenarios where models have already been synced
    """
    def test_already_synced_superuser_view_models_are_built_if_superuser(self):
        self._create_sync_event(MODEL_FLAGS)

        view_models = build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link, {}, {},
                                                                  {}, {}, {}, {}, pytz.UTC, is_superuser=True)
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + len(SUPERUSER_DATA_MODELS)
        self.assertEqual(expected_length, len(view_models))

    def test_already_synced_superuser_view_models_are_not_built_if_not_superuser(self):
        # this is an important one
        # ensures an already synced view model is not included if user does not have access
        self._create_sync_event(MODEL_FLAGS)

        view_models = build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link, {}, {},
                                                                  {}, {}, {}, {}, pytz.UTC, is_superuser=False)
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS)
        self.assertEqual(expected_length, len(view_models))

    def test_already_synced_app_view_models_are_built(self):
        self._create_sync_event(MODEL_APP, AppLinkDetail(app_id=self.linked_app._id).to_json())

        _, downstream_apps = get_upstream_and_downstream_apps(self.downstream_domain)
        view_models = build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link,
                                                                  downstream_apps, {}, {}, {}, {}, {}, pytz.UTC)
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def test_linked_apps_are_popped(self):
        self._create_sync_event(MODEL_APP, AppLinkDetail(app_id=self.linked_app._id).to_json())

        _, downstream_apps = get_upstream_and_downstream_apps(self.downstream_domain)
        self.assertTrue(1, len(downstream_apps))
        build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link, downstream_apps, {},
                                                    {}, {}, {}, {}, pytz.UTC)
        self.assertEqual(0, len(downstream_apps))

    def test_already_synced_fixture_view_models_are_built(self):
        self._create_sync_event(MODEL_FIXTURE, FixtureLinkDetail(tag=self.original_fixture.tag).to_json())

        _, downstream_fixtures = get_upstream_and_downstream_fixtures(self.downstream_domain, self.domain_link)
        view_models = build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link, {},
                                                                  downstream_fixtures, {}, {}, {}, {}, pytz.UTC)
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def test_linked_fixtures_are_popped(self):
        self._create_sync_event(MODEL_FIXTURE, FixtureLinkDetail(tag=self.original_fixture.tag).to_json())

        _, downstream_fixtures = get_upstream_and_downstream_fixtures(self.downstream_domain, self.domain_link)
        self.assertTrue(1, len(downstream_fixtures))
        build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link, {},
                                                    downstream_fixtures, {}, {}, {}, {}, pytz.UTC)
        self.assertEqual(0, len(downstream_fixtures))

    def test_already_synced_report_view_models_are_built(self):
        self._create_sync_event(MODEL_REPORT, ReportLinkDetail(report_id=self.linked_report.get_id).to_json())

        _, downstream_reports = get_upstream_and_downstream_reports(self.downstream_domain)
        view_models = build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link, {}, {},
                                                                  downstream_reports, {}, {}, {}, pytz.UTC)
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def test_linked_reports_are_popped(self):
        self._create_sync_event(MODEL_REPORT, ReportLinkDetail(report_id=self.linked_report.get_id).to_json())

        _, downstream_reports = get_upstream_and_downstream_reports(self.downstream_domain)
        self.assertTrue(1, len(downstream_reports))
        build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link, {}, {},
                                                    downstream_reports, {}, {}, {}, pytz.UTC)
        self.assertEqual(0, len(downstream_reports))

    def test_already_synced_keyword_view_models_are_built(self):
        self._create_sync_event(MODEL_KEYWORD, KeywordLinkDetail(keyword_id=str(self.linked_keyword.id)).to_json())

        _, downstream_keywords = get_upstream_and_downstream_keywords(self.downstream_domain)
        self.assertTrue(1, len(downstream_keywords))
        view_models = build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link, {}, {},
                                                                  {}, downstream_keywords, {}, {}, pytz.UTC)
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def test_linked_keywords_are_popped(self):
        self._create_sync_event(MODEL_KEYWORD, KeywordLinkDetail(keyword_id=str(self.linked_keyword.id)).to_json())

        _, downstream_keywords = get_upstream_and_downstream_keywords(self.downstream_domain)
        self.assertTrue(1, len(downstream_keywords))
        build_pullable_view_models_from_data_models(self.downstream_domain, self.domain_link, {}, {}, {},
                                                    downstream_keywords, {}, {}, pytz.UTC)
        self.assertEqual(0, len(downstream_keywords))

    def test_already_synced_update_rules_are_built(self):
        update_rule = _create_update_rule(self.upstream_domain,
                            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, should_save=True)
        self._create_sync_event(MODEL_AUTO_UPDATE_RULE, UpdateRuleLinkDetail(id=update_rule.id).to_json())

        upstream_rules, _ = get_upstream_and_downstream_update_rules(self.upstream_domain, self.domain_link)
        view_models = build_pullable_view_models_from_data_models(self.upstream_domain, self.domain_link,
                                                                  {}, {}, {}, {}, {}, upstream_rules, pytz.UTC)
        expected_length = len(DOMAIN_LEVEL_DATA_MODELS) + 1
        self.assertEqual(expected_length, len(view_models))

    def _create_sync_event(self, model_type, model_detail=None):
        sync_event = DomainLinkHistory(
            link=self.domain_link, date=datetime.utcnow(), model=model_type, model_detail=model_detail
        )
        sync_event.save()


class PopDataModelsTests(TestCase):

    def test_pop_app_returns_none_if_does_not_exist(self):
        self.assertIsNone(pop_app('unknown', {}))

    def test_pop_fixture_returns_none_if_does_not_exist(self):
        self.assertIsNone(pop_fixture('unknown', {}, 'pop-test'))

    def test_pop_report_returns_none_if_does_not_exist(self):
        self.assertIsNone(pop_report('unknown', {}))

    def test_pop_keyword_returns_none_if_does_not_exist(self):
        self.assertIsNone(pop_keyword(0, {}))

    def test_pop_ucr_expression_returns_none_if_does_not_exist(self):
        self.assertIsNone(pop_ucr_expression(0, {}))
