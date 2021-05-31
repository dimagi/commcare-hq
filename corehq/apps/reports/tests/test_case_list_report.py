from django.http.request import QueryDict
from django.test import TestCase
from django.test.client import RequestFactory

from casexml.apps.case.models import CommCareCase
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    DomainMembership,
    WebUser,
)
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.mappings.case_mapping import CASE_INDEX, CASE_INDEX_INFO
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.pillows.user import transform_user_for_elasticsearch
from corehq.util.elastic import ensure_index_deleted


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
                user_obj.delete('')
        cls.user_list = []
        for user in dummy_user_list:
            user_obj = CommCareUser.create(**user) if user['doc_type'] == 'CommcareUser'\
                else WebUser.create(**user)
            user_obj.save()
            cls.user_list.append(user_obj)

        cls.case_list = []
        for case in dummy_case_list:
            cls.case_list.append(CommCareCase(**case))
        cls.es = get_es_new()
        ensure_index_deleted(USER_INDEX)
        ensure_index_deleted(CASE_INDEX)
        initialize_index_and_mapping(cls.es, USER_INDEX_INFO)
        initialize_index_and_mapping(cls.es, CASE_INDEX_INFO)
        initialize_index_and_mapping(cls.es, GROUP_INDEX_INFO)
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
        ensure_index_deleted(USER_INDEX)
        ensure_index_deleted(CASE_INDEX)
        for user in cls.user_list:
            user.delete(deleted_by='')
        super().tearDownClass()

    @classmethod
    def _send_users_to_es(cls):
        for user_obj in cls.user_list:
            send_to_elasticsearch('users', transform_user_for_elasticsearch(user_obj.to_json()))
        cls.es.indices.refresh(USER_INDEX)

    @classmethod
    def _send_cases_to_es(cls):
        for case in cls.case_list:
            send_to_elasticsearch('cases', case.to_json())
        cls.es.indices.refresh(CASE_INDEX_INFO.index)

    def test_with_project_data_slug(self):
        report_slugs = ['project_data']
        q_dict_get = QueryDict('', mutable=True)
        q_dict_get.setlist('case_list_filter', report_slugs)
        self.request.GET = q_dict_get
        data = CaseListReport(self.request, domain=self.domain).es_results['hits'].get('hits', [])
        expected_case_ids = ['id-1', 'id-2', 'id-3', 'id-5']
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
