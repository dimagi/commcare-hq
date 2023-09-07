import json
from django.http.request import QueryDict
from django.test import TestCase
from django.test.client import RequestFactory

from corehq.apps.domain.models import Domain
from corehq.apps.reports.standard.cases.case_list_explorer import CaseListExplorer
from corehq.apps.users.models import (
    DomainMembership,
    WebUser,
)
from corehq.util.test_utils import privilege_enabled


class TestCaseListExplorer(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_name = 'case-list-test'
        cls.domain = Domain.get_or_create_with_name(cls.domain_name, is_active=True)
        cls.user = WebUser(username='test@cchq.com', domains=[cls.domain_name], is_admin=True)
        cls.user.domain_memberships.append(DomainMembership(domain=cls.domain_name, role_id='admin'))
        cls.request_factory = RequestFactory()

    def setUp(self):
        super().setUp()
        self.request = self.request_factory.get('/some/url')
        self.request.couch_user = self.user
        self.request.domain = self.domain
        self.request.can_access_all_locations = True

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.domain.delete()

    @privilege_enabled('CASE_LIST_EXPLORER')
    def test_with_explorer_columns_legacy(self):
        legacy_columns = ['@case_type', 'case_name', 'last_modified']
        get_query_dict = QueryDict('', mutable=True)
        report_slugs = ['project_data']
        get_query_dict.setlist('case_list_filter', report_slugs)

        # CaseListExplorerColumns expects an encoded json string
        get_query_dict['explorer_columns'] = json.dumps(legacy_columns)

        self.request.GET = get_query_dict
        cle = CaseListExplorer(self.request, domain=self.domain_name)

        header_names = []
        header_prop_names = []

        for header in cle.headers:
            header_names.append(header.html)
            header_prop_names.append(header.prop_name)

        for column in legacy_columns:
            self.assertIn(column, header_names)
            self.assertIn(column, header_prop_names)

    @privilege_enabled('CASE_LIST_EXPLORER')
    def test_with_explorer_columns(self):
        columns = [
            {'name': '@case_type', 'label': '@case_type'},
            {'name': 'case_name', 'label': 'case_name'},
            {'name': 'last_modified', 'label': 'last_modified'}
        ]
        get_query_dict = QueryDict('', mutable=True)
        report_slugs = ['project_data']
        get_query_dict.setlist('case_list_filter', report_slugs)
        get_query_dict['explorer_columns'] = json.dumps(columns)

        self.request.GET = get_query_dict
        cle = CaseListExplorer(self.request, domain=self.domain_name)

        header_names = []
        header_prop_names = []

        for header in cle.headers:
            header_names.append(header.html)
            header_prop_names.append(header.prop_name)

        for column in columns:
            self.assertIn(column['name'], header_names)
            self.assertIn(column['label'], header_prop_names)
