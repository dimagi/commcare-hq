import uuid

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.reports.views import _get_cases_with_other_forms
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils

DOMAIN = 'test-form-archive'


class TestGetCasesWithOtherForms(TestCase):

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(DOMAIN)
        super().tearDown()

    def test_creating_form_with_no_other_forms(self):
        case_id = uuid.uuid4().hex
        create_form = self._submit(CaseBlock(case_id, create=True, case_name='Ann'))
        assert _get_cases_with_other_forms(DOMAIN, create_form) == {}

    def test_creating_form_with_a_followup_form(self):
        case_id = uuid.uuid4().hex
        create_form = self._submit(CaseBlock(case_id, create=True, case_name='Ann'))
        self._submit(CaseBlock(case_id, update={'color': 'red'}))
        assert _get_cases_with_other_forms(DOMAIN, create_form) == {case_id: 'Ann'}

    def test_followup_form_that_creates_an_existing_case(self):
        case_id = uuid.uuid4().hex
        self._submit(CaseBlock(case_id, create=True, case_name='Ann'))
        followup_form = self._submit(
            CaseBlock(case_id, create=True, case_name='Ann', update={'color': 'red'}))
        assert _get_cases_with_other_forms(DOMAIN, followup_form) == {}

    def test_creating_form_that_arrives_after_an_update(self):
        case_id = uuid.uuid4().hex
        # an update for a case that does not exist yet opens the case, so the
        # create block that follows it only updates the case
        self._submit(CaseBlock(case_id, update={'color': 'red'}))
        create_form = self._submit(CaseBlock(case_id, create=True, case_name='Ann'))
        assert _get_cases_with_other_forms(DOMAIN, create_form) == {}

    def test_creating_form_whose_followup_form_is_archived(self):
        case_id = uuid.uuid4().hex
        create_form = self._submit(CaseBlock(case_id, create=True, case_name='Ann'))
        followup_form = self._submit(CaseBlock(case_id, update={'color': 'red'}))
        followup_form.archive(user_id='tester')
        assert _get_cases_with_other_forms(DOMAIN, create_form) == {}

    def test_deleted_case(self):
        case_id = uuid.uuid4().hex
        create_form = self._submit(CaseBlock(case_id, create=True, case_name='Ann'))
        self._submit(CaseBlock(case_id, update={'color': 'red'}))
        CommCareCase.objects.soft_delete_cases(DOMAIN, [case_id])
        assert _get_cases_with_other_forms(DOMAIN, create_form) == {}

    def test_case_in_another_domain(self):
        case_id = uuid.uuid4().hex
        create_form = self._submit(CaseBlock(case_id, create=True, case_name='Ann'))
        self._submit(CaseBlock(case_id, update={'color': 'red'}))
        assert _get_cases_with_other_forms('other-domain', create_form) == {}

    def _submit(self, case_block):
        form, _ = submit_case_blocks([case_block.as_text()], DOMAIN)
        return form


class TestUnarchiveFormView(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(DOMAIN)
        cls.addClassCleanup(cls.project.delete)
        cls.admin = WebUser.create(DOMAIN, 'unarchive-admin', 'password', None, None, is_admin=True)
        cls.addClassCleanup(cls.admin.delete, DOMAIN, deleted_by=None)

    def setUp(self):
        form, _ = submit_case_blocks(
            [CaseBlock(uuid.uuid4().hex, create=True, case_name='Ann').as_text()], DOMAIN)
        form.archive(user_id='tester')
        self.form_id = form.form_id
        self.url = reverse('unarchive_form', args=[DOMAIN, self.form_id])
        self.client.login(username='unarchive-admin', password='password')

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(DOMAIN)
        super().tearDown()

    def test_get_is_rejected(self):
        response = self.client.get(self.url)
        assert response.status_code == 405
        assert XFormInstance.objects.get_form(self.form_id, DOMAIN).is_archived

    def test_post_restores_form(self):
        response = self.client.post(self.url)
        assert response.status_code == 302
        assert not XFormInstance.objects.get_form(self.form_id, DOMAIN).is_archived

    def test_post_redirects_to_same_site_referer(self):
        referer = f'http://testserver/a/{DOMAIN}/reports/'
        response = self.client.post(self.url, HTTP_REFERER=referer)
        assert response['Location'] == referer

    def test_post_ignores_off_site_referer(self):
        response = self.client.post(self.url, HTTP_REFERER='https://example.com/')
        assert response['Location'] == reverse('render_form_data', args=[DOMAIN, self.form_id])
