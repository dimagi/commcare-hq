import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.reports.views import _get_cases_with_other_forms
from corehq.form_processor.models import CommCareCase
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
