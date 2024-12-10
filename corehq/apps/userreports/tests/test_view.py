import uuid
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.http import HttpRequest
from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test, populate_case_search_index
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.userreports import tasks
from corehq.apps.userreports.const import DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.exceptions import (
    BadBuilderConfigError,
    DataSourceConfigurationNotFoundError,
    UserReportsError,
)
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.reports.view import ConfigurableReportView
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.userreports.views import (
    _number_of_records_to_be_iterated_for_rebuild,
)
from corehq.apps.users.models import HQApiKey, HqPermissions, UserRole, WebUser
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.signals import sql_case_post_save
from corehq.motech.const import OAUTH2_CLIENT
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import DataSourceRepeater
from corehq.sql_db.connections import Session
from corehq.util.context_managers import drop_connected_signals
from corehq.util.test_utils import flag_enabled


class ConfigurableReportTestMixin(object):
    domain = "TEST_DOMAIN"
    case_type = "CASE_TYPE"

    @classmethod
    def _sample_data_source_config(cls):
        return DataSourceConfiguration(
            domain=cls.domain,
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id="woop_woop",
            configured_filter={
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "property_value": cls.case_type,
            },
            configured_indicators=[
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'fruit'
                    },
                    "column_id": 'indicator_col_id_fruit',
                    "display_name": 'indicator_display_name_fruit',
                    "datatype": "string"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'num1'
                    },
                    "column_id": 'indicator_col_id_num1',
                    "datatype": "integer"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'num2'
                    },
                    "column_id": 'indicator_col_id_num2',
                    "datatype": "integer"
                },
            ],
        )

    @classmethod
    def _new_case(cls, properties):
        id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=id,
            case_type=cls.case_type,
            update=properties,
        ).as_text()
        with drop_connected_signals(sql_case_post_save):
            submit_case_blocks(case_block, domain=cls.domain)
        return CommCareCase.objects.get_case(id, cls.domain)

    @classmethod
    def _delete_everything(cls):
        delete_all_cases()
        for config in DataSourceConfiguration.all():
            config.delete()
        delete_all_report_configs()


class ConfigurableReportViewTest(ConfigurableReportTestMixin, TestCase):

    def _build_report_and_view(self, request=HttpRequest()):
        # Create report
        data_source_config = self._sample_data_source_config()
        data_source_config.validate()
        data_source_config.save()
        self.addCleanup(data_source_config.delete)
        tasks.rebuild_indicators(data_source_config._id)
        adapter = get_indicator_adapter(data_source_config)
        self.addCleanup(adapter.drop_table)

        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_config._id,
            title='foo',
            aggregation_columns=['doc_id'],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_fruit",
                    "field": 'indicator_col_id_fruit',
                    'column_id': 'report_column_col_id_fruit',
                    'aggregation': 'simple'
                },
                {
                    "type": "percent",
                    "display": "report_column_display_percent",
                    'column_id': 'report_column_col_id_percent',
                    'format': 'percent',
                    "denominator": {
                        "type": "field",
                        "aggregation": "sum",
                        "field": "indicator_col_id_num1",
                        "column_id": "report_column_col_id_percent_num1"
                    },
                    "numerator": {
                        "type": "field",
                        "aggregation": "sum",
                        "field": "indicator_col_id_num2",
                        "column_id": "report_column_col_id_percent_num2"
                    }
                },
                {
                    "type": "expanded",
                    "display": "report_column_display_expanded_num1",
                    "field": 'indicator_col_id_num1',
                    'column_id': 'report_column_col_id_expanded_num1',
                }
            ],
            configured_charts=[
                {
                    "type": 'pie',
                    "value_column": 'count',
                    "aggregation_column": 'fruit',
                    "title": 'Fruits'
                },
                {
                    "type": 'multibar',
                    "title": 'Fruit Properties',
                    "x_axis_column": 'fruit',
                    "y_axis_columns": [
                        {"column_id": "report_column_col_id_expanded_num1", "display": "Num1 values"}
                    ]
                },

            ]
        )
        report_config.save()
        self.addCleanup(report_config.delete)

        view = ConfigurableReportView(request=request)
        view._domain = self.domain
        view._lang = "en"
        view._report_config_id = report_config._id

        return report_config, view

    @classmethod
    def tearDownClass(cls):
        # todo: understand why this is necessary. the view call uses the session and the
        # signal doesn't fire to kill it.
        Session.remove()
        super().tearDownClass()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cases = []
        cls.cases.append(cls._new_case({'fruit': 'apple', 'num1': 4, 'num2': 6}))
        cls.cases.append(cls._new_case({'fruit': 'mango', 'num1': 7, 'num2': 4}))
        cls.cases.append(cls._new_case({'fruit': 'unknown', 'num1': 1, 'num2': 0}))

    def test_export_table(self):
        """
        Test the output of ConfigurableReportView.export_table()
        """
        report, view = self._build_report_and_view()
        expected = [
            [
                'foo',
                [
                    [
                        'report_column_display_fruit',
                        'report_column_display_percent',
                        'report_column_display_expanded_num1-1',
                        'report_column_display_expanded_num1-4',
                        'report_column_display_expanded_num1-7',
                    ],
                    ['apple', '150%', 0, 1, 0],
                    ['mango', '57%', 0, 0, 1],
                    ['unknown', '0%', 1, 0, 0]
                ]
            ]
        ]
        self.assertEqual(view.export_table, expected)

    def test_report_preview_data(self):
        """
        Test the output of ConfigurableReportView.export_table()
        """
        report, view = self._build_report_and_view()

        actual = ConfigurableReportView.report_preview_data(report.domain, report)
        expected = {
            "table": [
                [
                    'report_column_display_fruit',
                    'report_column_display_percent',
                    'report_column_display_expanded_num1-1',
                    'report_column_display_expanded_num1-4',
                    'report_column_display_expanded_num1-7',
                ],
                ['apple', '150%', 0, 1, 0],
                ['mango', '57%', 0, 0, 1],
                ['unknown', '0%', 1, 0, 0]
            ],
            "map_config": report.map_config,
            "chart_configs": report.charts,
            "aaData": [
                {
                    "report_column_col_id_fruit": "apple",
                    "report_column_col_id_percent": "150%",
                    'report_column_col_id_expanded_num1-0': 0,
                    'report_column_col_id_expanded_num1-1': 1,
                    'report_column_col_id_expanded_num1-2': 0,
                },
                {
                    'report_column_col_id_fruit': 'mango',
                    'report_column_col_id_percent': '57%',
                    'report_column_col_id_expanded_num1-0': 0,
                    'report_column_col_id_expanded_num1-1': 0,
                    'report_column_col_id_expanded_num1-2': 1,
                },
                {
                    'report_column_col_id_fruit': 'unknown',
                    'report_column_col_id_percent': '0%',
                    'report_column_col_id_expanded_num1-0': 1,
                    'report_column_col_id_expanded_num1-1': 0,
                    'report_column_col_id_expanded_num1-2': 0,
                }
            ]
        }
        self.assertEqual(actual, expected)

    def test_report_preview_data_with_expanded_columns(self):
        report, view = self._build_report_and_view()
        multibar_chart = report.charts[1].to_json()
        self.assertEqual(multibar_chart['type'], 'multibar')
        self.assertEqual(
            multibar_chart['y_axis_columns'],
            [
                {
                    'column_id': 'report_column_col_id_expanded_num1',
                    'display': 'Num1 values'
                }
            ]
        )

        with flag_enabled('SUPPORT_EXPANDED_COLUMN_IN_REPORTS'):
            report, view = self._build_report_and_view()
            multibar_chart = report.charts[1].to_json()
            self.assertEqual(multibar_chart['type'], 'multibar')
            self.assertEqual(
                multibar_chart['y_axis_columns'],
                [
                    {
                        'column_id': 'report_column_col_id_expanded_num1-0',
                        'display': 'report_column_display_expanded_num1-1'
                    },
                    {
                        'column_id': 'report_column_col_id_expanded_num1-1',
                        'display': 'report_column_display_expanded_num1-4'
                    },
                    {
                        'column_id': 'report_column_col_id_expanded_num1-2',
                        'display': 'report_column_display_expanded_num1-7'
                    },
                ]
            )

            # just test that preview works
            self.test_report_preview_data()

    def test_report_charts(self):
        report, view = self._build_report_and_view()

        preview_data = ConfigurableReportView.report_preview_data(report.domain, report)
        preview_data_pie_chart = preview_data['chart_configs'][0]
        self.assertEqual(preview_data_pie_chart.type, 'pie')
        self.assertEqual(preview_data_pie_chart.title, 'Fruits')
        self.assertEqual(preview_data_pie_chart.value_column, 'count')
        self.assertEqual(preview_data_pie_chart.aggregation_column, 'fruit')

        preview_data_multibar_chart = preview_data['chart_configs'][1]
        self.assertEqual(preview_data_multibar_chart.type, 'multibar')
        self.assertEqual(preview_data_multibar_chart.title, 'Fruit Properties')
        self.assertEqual(preview_data_multibar_chart.title, 'Fruit Properties')
        self.assertEqual(preview_data_multibar_chart.x_axis_column, 'fruit')
        self.assertEqual(
            preview_data_multibar_chart.y_axis_columns[0].column_id,
            'report_column_col_id_expanded_num1'
        )
        self.assertEqual(
            preview_data_multibar_chart.y_axis_columns[0].display,
            'Num1 values'
        )

    @flag_enabled('SUPPORT_EXPANDED_COLUMN_IN_REPORTS')
    def test_report_charts_with_expanded_columns(self):
        report, view = self._build_report_and_view()

        preview_data = ConfigurableReportView.report_preview_data(report.domain, report)
        multibar_chart = preview_data['chart_configs'][1].to_json()
        self.assertEqual(multibar_chart['type'], 'multibar')
        self.assertEqual(
            multibar_chart['y_axis_columns'],
            [
                {
                    'column_id': 'report_column_col_id_expanded_num1-0',
                    'display': 'report_column_display_expanded_num1-1'
                },
                {
                    'column_id': 'report_column_col_id_expanded_num1-1',
                    'display': 'report_column_display_expanded_num1-4'
                },
                {
                    'column_id': 'report_column_col_id_expanded_num1-2',
                    'display': 'report_column_display_expanded_num1-7'
                },
            ]
        )

    @patch("corehq.apps.userreports.reports.view.ReportExport")
    def test_report_preview_data_does_not_handle_user_reports_error(self, mock):
        mock.side_effect = UserReportsError
        report, view = self._build_report_and_view()

        with self.assertRaises(UserReportsError):
            ConfigurableReportView.report_preview_data(report.domain, report)

    @patch("corehq.apps.userreports.reports.view.ReportExport")
    def test_report_preview_data_propagates_data_source_not_found_error(self, mock):
        mock.side_effect = DataSourceConfigurationNotFoundError
        report, view = self._build_report_and_view()

        with self.assertRaises(BadBuilderConfigError) as err:
            ConfigurableReportView.report_preview_data(report.domain, report)
        self.assertEqual(str(err.exception), DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE)

    def test_paginated_build_table(self):
        """
        Simulate building a report where chunking occurs
        """

        with patch('corehq.apps.userreports.tasks.ID_CHUNK_SIZE', 1):
            report, view = self._build_report_and_view()
        expected = [
            [
                'foo',
                [
                    [
                        'report_column_display_fruit',
                        'report_column_display_percent',
                        'report_column_display_expanded_num1-1',
                        'report_column_display_expanded_num1-4',
                        'report_column_display_expanded_num1-7',
                    ],
                    ['apple', '150%', 0, 1, 0],
                    ['mango', '57%', 0, 0, 1],
                    ['unknown', '0%', 1, 0, 0]
                ]
            ]
        ]
        self.assertEqual(view.export_table, expected)

    def test_redirect_custom_report(self):
        report, view = self._build_report_and_view()
        request = HttpRequest()
        self.assertFalse(view.should_redirect_to_paywall(request))

    def test_redirect_report_builder(self):
        report, view = self._build_report_and_view()
        report.report_meta.created_by_builder = True
        report.save()
        request = HttpRequest()
        self.assertTrue(view.should_redirect_to_paywall(request))

    def test_can_edit_report(self):
        """
        Test whether ConfigurableReportView.page_context allows report editing
        """
        domain = Domain(name='test_domain', is_active=True)
        domain.save()
        self.addCleanup(domain.delete)

        def create_view(can_edit_reports):
            rolename = 'edit_role' if can_edit_reports else 'view_role'
            username = 'editor' if can_edit_reports else 'viewer'
            toggles.USER_CONFIGURABLE_REPORTS.set(username, True, toggles.NAMESPACE_USER)

            # user_role should be deleted along with the domain.
            user_role = UserRole.create(
                domain=domain.name,
                name=rolename,
                permissions=HqPermissions(edit_commcare_users=True,
                                          view_commcare_users=True,
                                          edit_groups=True,
                                          view_groups=True,
                                          edit_locations=True,
                                          view_locations=True,
                                          access_all_locations=False,
                                          edit_data=True,
                                          edit_reports=can_edit_reports,
                                          view_reports=True
                                          )
            )

            web_user = WebUser.create(domain.name, username, '***', None, None)
            web_user.set_role(domain.name, user_role.get_qualified_id())
            web_user.current_domain = domain.name
            web_user.save()
            self.addCleanup(web_user.delete, domain.name, deleted_by=None)

            request = HttpRequest()
            request.can_access_all_locations = True
            request.user = web_user.get_django_user()
            request.couch_user = web_user
            request.session = {}
            _, view = self._build_report_and_view(request=request)
            return view

        cannot_edit_view = create_view(False)
        self.assertEqual(cannot_edit_view.page_context['can_edit_report'], False)

        can_edit_view = create_view(True)
        self.assertEqual(can_edit_view.page_context['can_edit_report'], True)


@es_test(requires=[case_search_adapter], setup_class=True)
class TestDataSourceRebuild(ConfigurableReportTestMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cases = [
            cls._new_case({'fruit': 'apple', 'num1': 4, 'num2': 6}),
            cls._new_case({'fruit': 'mango', 'num1': 7, 'num2': 4}),
            cls._new_case({'fruit': 'unknown', 'num1': 1, 'num2': 0})
        ]
        populate_case_search_index(cases)

        cls.data_source_config = cls._sample_data_source_config()
        cls.data_source_config.save()

    @classmethod
    def tearDownClass(cls):
        cls._delete_everything()
        super().tearDownClass()

    def _send_data_source_rebuild_request(self):
        path = reverse("rebuild_configurable_data_source", args=(self.domain, self.data_source_config.get_id))
        return self.client.post(path)

    def test_number_of_records_to_be_iterated_for_rebuild(self):
        number_of_cases = _number_of_records_to_be_iterated_for_rebuild(self.data_source_config)
        self.assertEqual(number_of_cases, 3)

    def test_feature_flag(self):
        response = self._send_data_source_rebuild_request()
        self.assertEqual(response.status_code, 404)

    @flag_enabled('USER_CONFIGURABLE_REPORTS')
    def test_successful_rebuilt(self):
        response = self._send_data_source_rebuild_request()
        self.assertEqual(response.status_code, 302)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(
            str(messages[0]),
            'Table "foo" is now being rebuilt. Data should start showing up soon'
        )

    @flag_enabled('USER_CONFIGURABLE_REPORTS')
    @flag_enabled('RESTRICT_DATA_SOURCE_REBUILD')
    def test_blocked_rebuild_for_restricted_data_source(self):
        with patch('corehq.apps.userreports.views.DATA_SOURCE_REBUILD_RESTRICTED_AT', 2):
            response = self._send_data_source_rebuild_request()

            self.assertEqual(response.status_code, 302)

            messages = list(get_messages(response.wsgi_request))
            self.assertEqual(
                str(messages[0]),
                (
                    'Rebuilt was not initiated due to high number of records this data source is expected to '
                    'iterate during a rebuild. Expected records to be processed is currently 3 '
                    'which is above the limit of 2. '
                    'Please consider creating a new data source instead or reach out to support if '
                    'you need to rebuild this data source.'
                )
            )

    @flag_enabled('USER_CONFIGURABLE_REPORTS')
    @flag_enabled('RESTRICT_DATA_SOURCE_REBUILD')
    def test_successful_rebuild_for_restricted_data_source(self):
        response = self._send_data_source_rebuild_request()

        self.assertEqual(response.status_code, 302)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(
            str(messages[0]),
            'Table "foo" is now being rebuilt. Data should start showing up soon'
        )


class TestSubscribeToDataSource(TestCase):

    urlname = "subscribe_to_configurable_data_source"
    domain = "test-domain"
    USERNAME = "username"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = Domain.get_or_create_with_name(cls.domain, is_active=True)

        cls.api_user_role = UserRole.create(
            cls.domain, 'api-user', permissions=HqPermissions(access_api=True, view_reports=True)
        )
        cls.user = WebUser.create(cls.domain, cls.USERNAME, "password", None, None,
                                  role_id=cls.api_user_role.get_id)
        cls.api_key, _ = HQApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user))
        cls.domain_api_key, _ = HQApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user),
                                                               name='domain-scoped',
                                                               domain=cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=cls.domain, deleted_by=None)
        cls.project.delete()
        super().tearDownClass()

    def _construct_api_auth_header(self, api_key):
        return f'ApiKey {self.USERNAME}:{api_key.plaintext_key}'

    def _post_request(self, domain, data_source_id, data, **extras):
        path = reverse("subscribe_to_configurable_data_source", args=(domain, data_source_id,))
        return self.client.post(path, data=data, **extras)

    @flag_enabled('SUPERSET_ANALYTICS')
    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_subscribe_successful(self):
        data_source_id = "data_source_id"
        client_id = "client_id"

        post_data = {
            'webhook_url': 'https://hostname.com/webhook',
            'client_id': client_id,
            'client_secret': 'client_secret',
            'token_url': 'https://hostname.com/token',
            'refresh_url': 'https://hostname.com/refresh',
        }
        response = self._post_request(
            domain=self.domain,
            data_source_id=data_source_id,
            data=post_data,
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )

        self.assertEqual(response.status_code, 201)

        conn_settings = ConnectionSettings.objects.get(client_id=client_id)
        self.assertEqual(conn_settings.name, "CommCare Analytics on hostname.com")
        self.assertEqual(conn_settings.auth_type, OAUTH2_CLIENT)

        repeater = DataSourceRepeater.objects.get(
            name="Data source data_source_id on hostname.com"
        )
        self.assertEqual(repeater.connection_settings_id, conn_settings.id)
        self.assertEqual(repeater.data_source_id, data_source_id)

    @flag_enabled('SUPERSET_ANALYTICS')
    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_subscribe_create_only_one_repeater_instance(self):
        data_source_id = "data_source_id"
        client_id = "client_id"

        post_data = {
            'webhook_url': 'https://hostname.com/webhook',
            'client_id': client_id,
            'client_secret': 'client_secret',
            'token_url': 'https://hostname.com/token',
            'refresh_url': 'https://hostname.com/refresh',
        }
        response = self._post_request(
            domain=self.domain,
            data_source_id=data_source_id,
            data=post_data,
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(response.status_code, 201)

        conn_settings = ConnectionSettings.objects.get(client_id=client_id)
        repeater_count = DataSourceRepeater.objects.filter(
            domain=self.domain,
            connection_settings_id=conn_settings.id,
            options={"data_source_id": data_source_id},
        ).count()
        self.assertEqual(repeater_count, 1)

        response = self._post_request(
            domain=self.domain,
            data_source_id=data_source_id,
            data=post_data,
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(response.status_code, 201)

        repeater_count = DataSourceRepeater.objects.filter(
            domain=self.domain,
            connection_settings_id=conn_settings.id,
            options={"data_source_id": data_source_id},
        ).count()
        self.assertEqual(repeater_count, 1)

        conn_settings_count = ConnectionSettings.objects.filter(client_id=client_id).count()
        self.assertEqual(conn_settings_count, 1)

    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_subscribe_unsuccessful_without_ff(self):
        data_source_id = "data_source_id"
        request = self._post_request(
            domain=self.domain,
            data_source_id=data_source_id,
            data={},
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(request.status_code, 404)

    @flag_enabled('SUPERSET_ANALYTICS')
    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_subscribe_unsuccessful_with_a_missing_param(self):
        data_source_id = "data_source_id"
        post_data = {
            'webhook_url': 'https://hostname.com/webhook',
            'client_secret': 'client_secret',
            'token_url': 'https://hostname.com/token',
            'refresh_url': 'https://hostname.com/refresh',
        }

        request = self._post_request(
            domain=self.domain,
            data_source_id=data_source_id,
            data=post_data,
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(request.status_code, 422)
        self.assertEqual(request.content.decode("utf-8"), "Missing parameters: client_id")

    @flag_enabled('SUPERSET_ANALYTICS')
    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_subscribe_unsuccessful_with_missing_params(self):
        data_source_id = "data_source_id"
        post_data = {
            'webhook_url': 'https://hostname.com/webhook',
            'client_secret': 'client_secret',
        }

        request = self._post_request(
            domain=self.domain,
            data_source_id=data_source_id,
            data=post_data,
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(request.status_code, 422)
        self.assertEqual(
            request.content.decode("utf-8"),
            "Missing parameters: client_id, token_url",
        )


class TestUnsubscribeFromDataSource(TestCase):

    DOMAIN = "test-domain"
    CLIENT_ID = "client_id"
    USERNAME = "username"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = Domain.get_or_create_with_name(cls.DOMAIN, is_active=True)

        cls.api_user_role = UserRole.create(
            cls.DOMAIN, 'api-user', permissions=HqPermissions(access_api=True, view_reports=True)
        )
        cls.user = WebUser.create(cls.DOMAIN, cls.USERNAME, "password", None, None,
                                  role_id=cls.api_user_role.get_id)
        cls.api_key, _ = HQApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user))
        cls.domain_api_key, _ = HQApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user),
                                                               name='domain-scoped',
                                                               domain=cls.DOMAIN)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=cls.DOMAIN, deleted_by=None)
        cls.project.delete()
        super().tearDownClass()

    def _construct_api_auth_header(self, api_key):
        return f'ApiKey {self.USERNAME}:{api_key.plaintext_key}'

    def _post_request(self, domain, data_source_id, data=None, **extras):
        path = reverse("unsubscribe_from_configurable_data_source", args=(domain, data_source_id,))
        return self.client.post(path, data=data, **extras)

    def _subscribe_to_datasource(self, datasource_id):
        conn_settings, __ = ConnectionSettings.objects.update_or_create(
            client_id=self.CLIENT_ID,
            defaults={
                'domain': self.DOMAIN,
                'name': "testy",
                'auth_type': "oauth2_client",
                'client_secret': 'client_secret',
                'url': "",
                'token_url': 'token_url',
            }
        )
        DataSourceRepeater.objects.create(
            name=f"{datasource_id} name",
            domain=self.DOMAIN,
            data_source_id=datasource_id,
            connection_settings_id=conn_settings.id,
        )

    @flag_enabled('SUPERSET_ANALYTICS')
    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_basic_unsubscribe_successful(self):
        data_source_id = "data_source_id"
        self._subscribe_to_datasource(data_source_id)

        conn_settings = ConnectionSettings.objects.get(client_id=self.CLIENT_ID)
        connection_settings_id = conn_settings.id

        repeaters = DataSourceRepeater.objects.filter(connection_settings_id=connection_settings_id)
        self.assertEqual(repeaters.count(), 1)

        response = self._post_request(
            domain=self.DOMAIN,
            data={"client_id": self.CLIENT_ID},
            data_source_id=data_source_id,
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(response.status_code, 200)

        repeaters = DataSourceRepeater.objects.filter(connection_settings_id=connection_settings_id)
        self.assertEqual(repeaters.count(), 0)
        self.assertEqual(ConnectionSettings.objects.filter(id=connection_settings_id).count(), 0)

    @flag_enabled('SUPERSET_ANALYTICS')
    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_unsubscribe_when_multiple_repeaters(self):
        data_source_id_1 = "data_source_id1"
        data_source_id_2 = "data_source_id2"
        self._subscribe_to_datasource(data_source_id_1)
        self._subscribe_to_datasource(data_source_id_2)

        conn_settings = ConnectionSettings.objects.get(client_id=self.CLIENT_ID)
        connection_settings_id = conn_settings.id

        repeaters = DataSourceRepeater.objects.filter(connection_settings_id=connection_settings_id)
        self.assertEqual(repeaters.count(), 2)

        response = self._post_request(
            domain=self.DOMAIN,
            data={"client_id": self.CLIENT_ID},
            data_source_id=data_source_id_1,
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(response.status_code, 200)

        repeaters = DataSourceRepeater.objects.filter(connection_settings_id=connection_settings_id)
        self.assertEqual(repeaters.count(), 1)
        self.assertEqual(ConnectionSettings.objects.filter(id=connection_settings_id).count(), 1)

    @flag_enabled('SUPERSET_ANALYTICS')
    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_missing_client_id(self):
        response = self._post_request(
            domain=self.DOMAIN,
            data={},
            data_source_id='datasource_id',
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.content.decode("utf-8"), "The client_id parameter is required")

    @flag_enabled('SUPERSET_ANALYTICS')
    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_invalid_client_id(self):
        response = self._post_request(
            domain=self.DOMAIN,
            data={'client_id': 'client_id'},
            data_source_id='datasource_id',
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.content.decode("utf-8"), "Invalid client_id")

    @flag_enabled('SUPERSET_ANALYTICS')
    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_invalid_data_source_id(self):
        self._subscribe_to_datasource('datasource_id')

        response = self._post_request(
            domain=self.DOMAIN,
            data={'client_id': 'client_id'},
            data_source_id='invalid_datasource_id',
            HTTP_AUTHORIZATION=self._construct_api_auth_header(self.domain_api_key),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.content.decode("utf-8"), "Invalid data source ID")
