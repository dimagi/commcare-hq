from __future__ import absolute_import, unicode_literals

import base64
import json
import uuid

from django.http import QueryDict
from django.urls import reverse
from django.utils.http import urlencode

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks

from corehq.apps.api.resources import v0_5
from corehq.apps.domain.models import Domain
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.users.models import WebUser

from .utils import APIResourceTest


class TestSimpleReportConfigurationResource(APIResourceTest):
    resource = v0_5.SimpleReportConfigurationResource
    api_name = "v0.5"

    @classmethod
    def setUpClass(cls):
        super(TestSimpleReportConfigurationResource, cls).setUpClass()

        cls.report_columns = [
            {
                "column_id": 'foo',
                "display": "foo display",
                "type": "field",
                "field": "my_field",
                "aggregation": "simple",
            },
            {
                "column_id": 'bar',
                "display": "bar display",
                "type": "field",
                "field": "my_field",
                "aggregation": "simple",
            },
            {
                "column_id": 'expand',
                "display": "expand display",
                "type": "expanded",
                "field": "my_field",
                "max_expansion": 10,
            }
        ]
        cls.report_filters = [
            {
                'datatype': 'integer',
                'field': 'my_field',
                'type': 'dynamic_choice_list',
                'slug': 'my_field_filter',
            },
            {
                'datatype': 'string',
                'field': 'my_other_field',
                'type': 'dynamic_choice_list',
                'slug': 'my_other_field_filter',
            }
        ]
        cls.report_title = "test report"

        cls.data_source = DataSourceConfiguration(
            domain=cls.domain.name,
            referenced_doc_type="XFormInstance",
            table_id=uuid.uuid4().hex,
        )
        cls.data_source.save()

        cls.report_configuration = ReportConfiguration(
            title=cls.report_title,
            domain=cls.domain.name,
            config_id=cls.data_source._id,
            columns=cls.report_columns,
            filters=cls.report_filters
        )
        cls.report_configuration.save()

        another_report_configuration = ReportConfiguration(
            domain=cls.domain.name, config_id=cls.data_source._id, columns=[], filters=[]
        )
        another_report_configuration.save()

    def test_get_detail(self):
        response = self._assert_auth_get_resource(
            self.single_endpoint(self.report_configuration._id))
        self.assertEqual(response.status_code, 200)
        response_dict = json.loads(response.content)
        filters = response_dict['filters']
        columns = response_dict['columns']

        self.assertEqual(
            set(response_dict.keys()),
            {'resource_uri', 'filters', 'columns', 'id', 'title'}
        )

        self.assertEqual(
            [{
                "column_id": c['column_id'],
                "display": c['display'],
                "type": c['type']
            } for c in self.report_columns],
            columns
        )
        self.assertEqual(
            [{'datatype': x['datatype'], 'slug': x['slug'], 'type': x['type']} for x in self.report_filters],
            filters
        )
        self.assertEqual(response_dict['title'], self.report_title)

    def test_get_list(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        response_dict = json.loads(response.content)

        self.assertEqual(set(response_dict.keys()), {'meta', 'objects'})
        self.assertEqual(set(response_dict['meta'].keys()), {'total_count'})

        self.assertEqual(response_dict['meta']['total_count'], 2)
        self.assertEqual(len(response_dict['objects']), 2)

    def test_disallowed_methods(self):
        response = self._assert_auth_post_resource(
            self.single_endpoint(self.report_configuration._id),
            {},
            failure_code=405
        )
        self.assertEqual(response.status_code, 405)

    def test_auth(self):

        wrong_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        new_user = WebUser.create(wrong_domain.name, 'test', 'testpass')
        new_user.save()
        self.addCleanup(wrong_domain.delete)
        self.addCleanup(new_user.delete)

        response = self._assert_auth_get_resource(self.single_endpoint(self.report_configuration._id),
                                                  username='test', password='testpass')
        self.assertEqual(response.status_code, 403)  # 403 is "Forbidden"


class TestConfigurableReportDataResource(APIResourceTest):
    resource = v0_5.ConfigurableReportDataResource
    api_name = "v0.5"

    @classmethod
    def _get_list_endpoint(cls):
        return None

    def single_endpoint(self, id, get_params=None):
        endpoint = reverse('api_dispatch_detail', kwargs=dict(
            domain=self.domain.name,
            api_name=self.api_name,
            resource_name=self.resource._meta.resource_name,
            pk=id,
        ))
        if endpoint:
            endpoint += "?" + urlencode(get_params or {})
        return endpoint

    def setUp(self):
        credentials = base64.b64encode(
            "{}:{}".format(self.username, self.password).encode('utf-8')
        ).decode('utf-8')
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Basic ' + credentials

    @classmethod
    def setUpClass(cls):
        super(TestConfigurableReportDataResource, cls).setUpClass()

        case_type = "my_case_type"
        cls.field_name = "my_field"
        cls.case_property_values = ["foo", "foo", "bar", "baz"]

        cls.cases = []
        for val in cls.case_property_values:
            id = uuid.uuid4().hex
            case_block = CaseBlock(
                create=True,
                case_id=id,
                case_type=case_type,
                update={cls.field_name: val},
            ).as_xml()
            post_case_blocks([case_block], {'domain': cls.domain.name})
            cls.cases.append(CommCareCase.get(id))

        cls.report_columns = [
            {
                "column_id": cls.field_name,
                "type": "field",
                "field": cls.field_name,
                "aggregation": "simple",
            }
        ]
        cls.report_filters = [
            {
                'datatype': 'string',
                'field': cls.field_name,
                'type': 'dynamic_choice_list',
                'slug': 'my_field_filter',
            }
        ]

        cls.data_source = DataSourceConfiguration(
            domain=cls.domain.name,
            referenced_doc_type="CommCareCase",
            table_id=uuid.uuid4().hex,
            configured_filter={
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "property_value": case_type,
            },
            configured_indicators=[
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": cls.field_name
                    },
                    "column_id": cls.field_name,
                    "display_name": cls.field_name,
                    "datatype": "string"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": "opened_by"
                    },
                    "column_id": "opened_by",
                    "display_name": "opened_by",
                    "datatype": "string"
                },
            ],
        )
        cls.data_source.validate()
        cls.data_source.save()
        rebuild_indicators(cls.data_source._id)

        cls.report_configuration = ReportConfiguration(
            domain=cls.domain.name,
            config_id=cls.data_source._id,
            aggregation_columns=["doc_id"],
            columns=cls.report_columns,
            filters=cls.report_filters,
        )
        cls.report_configuration.save()

    def test_fetching_data(self):
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id))

        self.assertEqual(response.status_code, 200)
        response_dict = json.loads(response.content)

        self.assertEqual(response_dict["total_records"], len(self.cases))
        self.assertEqual(len(response_dict["data"]), len(self.cases))

    def test_expand_column_infos(self):

        aggregated_report = ReportConfiguration(
            domain=self.domain.name,
            config_id=self.data_source._id,
            aggregation_columns=["opened_by"],
            columns=[
                {
                    "column_id": self.field_name,
                    "type": "field",
                    "field": self.field_name,
                    "aggregation": "expand",
                }
            ],
            filters=[],
        )
        aggregated_report.save()

        response = self.client.get(
            self.single_endpoint(aggregated_report._id))
        response_dict = json.loads(response.content)
        columns = response_dict["columns"]

        for c in columns:
            self.assertIn("expand_column_value", c)
        self.assertSetEqual(set(self.case_property_values), {c['expand_column_value'] for c in columns})

    def test_page_size(self):
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id, {"limit": 1}))
        response_dict = json.loads(response.content)
        self.assertEqual(response_dict["total_records"], len(self.cases))
        self.assertEqual(len(response_dict["data"]), 1)

        response = self.client.get(
            self.single_endpoint(self.report_configuration._id, {"limit": 10000}))
        self.assertEqual(response.status_code, 400)

    def test_page_offset(self):
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id, {"offset": 2}))
        response_dict = json.loads(response.content)
        self.assertEqual(response_dict["total_records"], len(self.cases))
        self.assertEqual(len(response_dict["data"]), len(self.cases) - 2)

    def test_filtering(self):
        response = self.client.get(self.single_endpoint(
            self.report_configuration._id, {"my_field_filter": "foo"})
        )
        response_dict = json.loads(response.content)

        self.assertEqual(response_dict["total_records"], 2)

        response = self.client.get(self.single_endpoint(
            self.report_configuration._id, {"my_field_filter": "bar"})
        )
        response_dict = json.loads(response.content)

        self.assertEqual(response_dict["total_records"], 1)

    def test_next_page_url(self):
        # It's not the last page
        query_dict = QueryDict("", mutable=True)
        query_dict.update({"some_filter": "bar"})
        next = v0_5.ConfigurableReportDataResource(api_name=self.api_name)._get_next_page(
            self.domain.name, "123", 100, 50, 3450, query_dict)
        single_endpoint = self.single_endpoint("123", {"offset": 150, "limit": 50, "some_filter": "bar"})

        def _get_query_params(url):
            from six.moves.urllib.parse import parse_qs, urlparse
            return parse_qs(urlparse(url).query)

        self.assertEqual(next.split('?')[0], single_endpoint.split('?')[0])
        self.assertEqual(_get_query_params(next), _get_query_params(single_endpoint))

        # It's the last page
        next = v0_5.ConfigurableReportDataResource(api_name=self.api_name)._get_next_page(
            self.domain.name, "123", 100, 50, 120, query_dict)
        self.assertEqual(next, "")

    def test_auth_capital_username(self):
        capital_username_credentials = self._get_basic_credentials(self.username.upper(), self.password)
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id),
            HTTP_AUTHORIZATION='Basic ' + capital_username_credentials
        )
        self.assertEqual(response.status_code, 200)

    def test_auth_wrong_password(self):
        wrong_password_credentials = self._get_basic_credentials(self.username, 'wrong_password')
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id),
            HTTP_AUTHORIZATION='Basic ' + wrong_password_credentials
        )
        self.assertEqual(response.status_code, 401)  # 401 is "Unauthorized"

    def test_auth_wrong_domain(self):
        user_in_wrong_domain_name = 'mallory'
        user_in_wrong_domain_password = '1337haxor'
        wrong_domain_name = 'dvorak'

        wrong_domain = Domain.get_or_create_with_name(wrong_domain_name, is_active=True)
        self.addCleanup(wrong_domain.delete)
        user_in_wrong_domain = WebUser.create(
            wrong_domain_name, user_in_wrong_domain_name, user_in_wrong_domain_password
        )
        self.addCleanup(user_in_wrong_domain.delete)

        user_in_wrong_domain_credentials = self._get_basic_credentials(
            user_in_wrong_domain_name, user_in_wrong_domain_password
        )
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id),
            HTTP_AUTHORIZATION='Basic ' + user_in_wrong_domain_credentials
        )
        self.assertEqual(response.status_code, 403)  # 403 is "Forbidden"

    @staticmethod
    def _get_basic_credentials(username, password):
        return base64.b64encode(
            "{}:{}".format(
                username, password
            ).encode('utf-8')
        ).decode('utf-8')
