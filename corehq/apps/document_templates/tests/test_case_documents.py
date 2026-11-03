import pytest
from django.test import SimpleTestCase, TestCase

from corehq.apps.document_templates.case_documents import (
    MAX_CASES,
    CaseDocumentError,
    render_case_documents,
)
from corehq.apps.document_templates.models import Template
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    create_case,
    sharded,
)

DOMAIN = 'document-templates-test'
OTHER_DOMAIN = 'document-templates-other'


class TestCaseIdLimits(SimpleTestCase):

    def test_no_cases_is_an_error(self):
        with pytest.raises(CaseDocumentError, match='No cases'):
            render_case_documents(DOMAIN, [])

    def test_too_many_cases_is_an_error(self):
        with pytest.raises(CaseDocumentError, match=f'At most {MAX_CASES}'):
            render_case_documents(DOMAIN, [f'case-{i}' for i in range(MAX_CASES + 1)])


@sharded
class TestBuildCasePdf(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(FormProcessorTestUtils.delete_all_cases)
        Template.objects.create(
            domain=DOMAIN, name='Welcome', slug='welcome',
            variables={'body': {'type': 'markdown', 'value': 'Hello {{ first_name }}'}},
        )
        Template.objects.create(
            domain=OTHER_DOMAIN, name='Theirs', slug='theirs',
            variables={'body': {'type': 'markdown', 'value': 'Theirs'}},
        )

    def _case(self, domain=DOMAIN, **case_json):
        return create_case(domain, save=True, case_type='patient', case_json=case_json)

    def _build(self, *cases, domain=DOMAIN):
        return render_case_documents(domain, [case.case_id for case in cases])

    def test_each_case_is_rendered_with_its_own_properties_in_order(self):
        alice = self._case(document_template_slug='welcome', first_name='Alice')
        bob = self._case(document_template_slug='welcome', first_name='Bob')
        documents = self._build(bob, alice)
        assert ['Hello Bob' in documents[0], 'Hello Alice' in documents[1]] == [True, True]

    def test_repeated_case_ids_are_rendered_once(self):
        alice = self._case(document_template_slug='welcome', first_name='Alice')
        documents = self._build(alice, alice)
        assert len(documents) == 1

    def test_case_without_a_slug_fails_the_request(self):
        good = self._case(document_template_slug='welcome', first_name='Alice')
        bad = self._case(first_name='Bob')
        with pytest.raises(CaseDocumentError, match=bad.case_id) as error:
            self._build(good, bad)
        assert good.case_id not in str(error.value)

    def test_unknown_slug_fails_the_request(self):
        case = self._case(document_template_slug='nope', first_name='Alice')
        with pytest.raises(CaseDocumentError, match=case.case_id):
            self._build(case)

    def test_template_of_another_domain_is_not_used(self):
        case = self._case(document_template_slug='theirs')
        with pytest.raises(CaseDocumentError, match=case.case_id):
            self._build(case)

    def test_case_of_another_domain_is_not_found(self):
        case = self._case(domain=OTHER_DOMAIN, document_template_slug='theirs')
        with pytest.raises(CaseDocumentError, match=f'not found: {case.case_id}'):
            self._build(case)

    def test_unknown_case_id_is_not_found(self):
        with pytest.raises(CaseDocumentError, match='not found: nope'):
            render_case_documents(DOMAIN, ['nope'])

    def test_missing_variable_fails_with_the_case_id(self):
        case = self._case(document_template_slug='welcome')
        with pytest.raises(CaseDocumentError, match=f'{case.case_id}.*first_name'):
            self._build(case)
