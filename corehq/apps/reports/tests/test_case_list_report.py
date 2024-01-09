from django.http.request import QueryDict
from django.test import TestCase
from django.test.client import RequestFactory

from corehq.apps.es.cases import case_adapter
from corehq.apps.es.groups import group_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    DomainMembership,
    WebUser,
)
from corehq.form_processor.models import CommCareCase


@es_test(requires=[case_adapter, group_adapter, user_adapter], setup_class=True)
class TestCaseListReport(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'case-list-test'
        cls.user = WebUser(username='test@cchq.com', domains=[cls.domain])
        cls.user.domain_memberships = [DomainMembership(domain=cls.domain, role_id='admin')]
        cls.request_factory = RequestFactory()

        from corehq.apps.reports.tests.data.case_list_report_data import (
            dummy_case_list,
            dummy_user_list,
        )

        for user in dummy_user_list:
            user_obj = CouchUser.get_by_username(user['username'])
            if user_obj:
                user_obj.delete(cls.domain, deleted_by=None)
        cls.user_list = []
        for user in dummy_user_list:
            user_obj = CommCareUser.create(**user) if user['doc_type'] == 'CommcareUser'\
                else WebUser.create(**user)
            user_obj.save()
            cls.user_list.append(user_obj)

        cls.case_list = []
        for case in dummy_case_list:
            cls.case_list.append(CommCareCase(**case))
        cls._send_users_to_es()
        cls._send_cases_to_es()

    def setUp(self):
        super().setUp()
        self.request = self.request_factory.get('/some/url')
        self.request.couch_user = self.user
        self.request.domain = self.domain
        self.request.can_access_all_locations = True

    @classmethod
    def tearDownClass(cls):
        for user in cls.user_list:
            user.delete(cls.domain, deleted_by=None)
        super().tearDownClass()

    @classmethod
    def _send_users_to_es(cls):
        for user_obj in cls.user_list:
            user_adapter.index(user_obj, refresh=True)

    @classmethod
    def _send_cases_to_es(cls):
        case_adapter.bulk_index(cls.case_list, refresh=True)

    def test_with_project_data_slug(self):
        report_slugs = ['project_data']
        q_dict_get = QueryDict('', mutable=True)
        q_dict_get.setlist('case_list_filter', report_slugs)
        self.request.GET = q_dict_get
        data = CaseListReport(self.request, domain=self.domain).es_results['hits'].get('hits', [])
        expected_case_ids = ['id-1', 'id-2', 'id-3', 'id-4', 'id-5']
        queried_case_ids = [case['_id'] for case in data]
        self.assertCountEqual(expected_case_ids, queried_case_ids)

    def test_with_deactivated_slug(self):
        report_slugs = ['t__5']
        q_dict_get = QueryDict('', mutable=True)
        q_dict_get.setlist('case_list_filter', report_slugs)
        self.request.GET = q_dict_get
        data = CaseListReport(self.request, domain=self.domain).es_results['hits'].get('hits', [])
        expected_case_ids = ['id-1']
        queried_case_ids = [case['_id'] for case in data]
        self.assertCountEqual(expected_case_ids, queried_case_ids)

    def test_with_web_user_slug(self):
        report_slugs = ['t__6']
        q_dict_get = QueryDict('', mutable=True)
        q_dict_get.setlist('case_list_filter', report_slugs)
        self.request.GET = q_dict_get
        data = CaseListReport(self.request, domain=self.domain).es_results['hits'].get('hits', [])
        expected_case_ids = ['id-4']
        queried_case_ids = [case['_id'] for case in data]
        self.assertCountEqual(expected_case_ids, queried_case_ids)

    def test_with_multiple_slugs(self):
        report_slugs = ['project_data', 't__6']
        q_dict_get = QueryDict('', mutable=True)
        q_dict_get.setlist('case_list_filter', report_slugs)
        self.request.GET = q_dict_get
        data = CaseListReport(self.request, domain=self.domain).es_results['hits'].get('hits', [])
        expected_case_ids = ['id-1', 'id-2', 'id-3', 'id-4', 'id-5']
        queried_case_ids = [case['_id'] for case in data]
        self.assertCountEqual(expected_case_ids, queried_case_ids)

    def test_with_slugs_and_user_ids(self):
        report_slugs = ['t__5', 'u__active1']
        q_dict_get = QueryDict('', mutable=True)
        q_dict_get.setlist('case_list_filter', report_slugs)
        self.request.GET = q_dict_get
        data = CaseListReport(self.request, domain=self.domain).es_results['hits'].get('hits', [])
        expected_case_ids = ['id-1', 'id-2', 'id-3']
        queried_case_ids = [case['_id'] for case in data]
        self.assertCountEqual(expected_case_ids, queried_case_ids)
