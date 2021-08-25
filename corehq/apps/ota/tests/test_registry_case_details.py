from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.fixtures import CaseDBFixture
from casexml.apps.case.mock import CaseFactory
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.registry.tests.utils import create_registry_for_test
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.util.test_utils import generate_cases


@use_sql_backend
class RegistryCaseDetailsTests(TestCase):
    domain = 'registry-case-details'

    @classmethod
    def setUpTestData(cls):
        cls.domain_object = create_domain(cls.domain)
        cls.user = CommCareUser.create(cls.domain, "user", "123", None, None)
        cls.registry = create_registry_for_test(cls.user.get_django_user(), cls.domain)
        cls.registry.schema = [{"case_type": "patient"}, {"case_type": "contact"}]
        cls.registry.save()

        cls.case = CaseFactory(cls.domain).create_case(case_type="patient")

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=None, deleted_by=None)
        xform_ids = CaseAccessorSQL.get_case_xform_ids(cls.case.case_id)
        CaseAccessorSQL.hard_delete_cases(cls.domain, [cls.case.case_id])
        FormAccessorSQL.hard_delete_forms(cls.domain, xform_ids)
        Domain.get_db().delete_doc(cls.domain_object)  # no need to run the full domain delete

    def setUp(self):
        self.client.login(username="user", password="123")

    def test_get_case_details(self):
        response_content = self._make_request({
            "registry": self.registry.slug, "case_id": self.case.case_id, "case_type": "patient",
        }, 200)
        self.assertEqual(CaseDBFixture(self.case).fixture.decode('utf8'), response_content)

    def test_get_case_details_missing_case(self):
        self._make_request({
            "registry": self.registry.slug, "case_id": "missing", "case_type": "patient",
        }, 404)

    def test_get_case_details_missing_registry(self):
        self._make_request({
            "registry": "not-a-registry", "case_id": self.case.case_id, "case_type": "patient",
        }, 404)

    def _make_request(self, params, expected_response_code):
        response = self.client.get(reverse('registry_case', args=[self.domain]), data=params)
        self.assertEqual(response.status_code, expected_response_code)
        return response.content.decode('utf8')


@generate_cases([
    ({}, "'case_id', 'case_type', 'registry' are required parameters"),
    ({"case_id": "a"}, "'case_type', 'registry' are required parameters"),
    ({"case_id": "a", "case_type": "b"}, "'registry' is a required parameter"),
], RegistryCaseDetailsTests)
def test_required_params(self, params, message):
    content = self._make_request(params, 400)
    self.assertEqual(content, message)
