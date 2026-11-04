from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase, TestCase

from corehq.apps.document_templates.case_documents import (
    MAX_CASES,
    CaseDocumentError,
    render_case_documents,
)
from corehq.apps.document_templates.models import Area, Template
from corehq.apps.document_templates.rendering import generate_document
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    create_case,
    sharded,
)

DOMAIN = 'document-templates-test'
OTHER_DOMAIN = 'document-templates-other'
OWNER_ID = 'user1'  # the owner create_case gives cases by default
GROUP_ID = 'group1'
USER = SimpleNamespace(get_owner_ids=lambda domain: [OWNER_ID, GROUP_ID])


class TestCaseIdLimits(SimpleTestCase):

    def test_no_cases_is_an_error(self):
        with pytest.raises(CaseDocumentError, match='No cases'):
            render_case_documents(DOMAIN, [], USER)

    def test_too_many_cases_is_an_error(self):
        with pytest.raises(CaseDocumentError, match=f'At most {MAX_CASES}'):
            render_case_documents(DOMAIN, [f'case-{i}' for i in range(MAX_CASES + 1)], USER)


@sharded
class TestBuildCasePdf(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(FormProcessorTestUtils.delete_all_cases)
        Template.objects.create(
            domain=DOMAIN, name='Welcome', slug='welcome',
            areas={'body': Area(value='Hello {{ first_name }}')},
        )
        Template.objects.create(
            domain=OTHER_DOMAIN, name='Theirs', slug='theirs',
            areas={'body': Area(value='Theirs')},
        )

    def _case(self, domain=DOMAIN, owner_id=OWNER_ID, closed=False, **case_json):
        return create_case(
            domain, save=True, case_type='patient', owner_id=owner_id, closed=closed, case_json=case_json,
        )

    def _build(self, *cases, domain=DOMAIN, user=USER):
        return render_case_documents(domain, [case.case_id for case in cases], user)

    def test_each_case_is_rendered_with_its_own_properties_in_order(self):
        alice = self._case(document_template_slug='welcome', first_name='Alice')
        bob = self._case(document_template_slug='welcome', first_name='Bob')
        with patch(
            'corehq.apps.document_templates.case_documents.generate_document', wraps=generate_document,
        ) as generate:
            pdf = self._build(bob, alice)
        assert [call.args[1]['first_name'] for call in generate.call_args_list] == ['Bob', 'Alice']
        assert pdf.startswith(b'%PDF')

    def test_repeated_case_ids_are_rendered_once(self):
        alice = self._case(document_template_slug='welcome', first_name='Alice')
        with patch(
            'corehq.apps.document_templates.case_documents.generate_document', wraps=generate_document,
        ) as generate:
            self._build(alice, alice)
        assert generate.call_count == 1

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

    def test_deleted_template_is_not_used(self):
        Template.objects.create(domain=DOMAIN, name='Retired', slug='retired', areas={}, deleted=True)
        case = self._case(document_template_slug='retired')
        with pytest.raises(CaseDocumentError, match=case.case_id):
            self._build(case)

    def test_live_template_is_used_over_a_deleted_one_with_the_same_slug(self):
        Template.objects.create(
            domain=DOMAIN, name='Old welcome', slug='welcome', deleted=True,
            areas={'body': Area(value='Old {{ first_name }}')},
        )
        case = self._case(document_template_slug='welcome', first_name='Alice')
        with patch(
            'corehq.apps.document_templates.case_documents.generate_document', wraps=generate_document,
        ) as generate:
            self._build(case)
        assert generate.call_args.args[0]['body'].value == 'Hello {{ first_name }}'

    def test_case_of_another_domain_is_not_found(self):
        case = self._case(domain=OTHER_DOMAIN, document_template_slug='theirs')
        with pytest.raises(CaseDocumentError, match=f'not found: {case.case_id}'):
            self._build(case)

    def test_unknown_case_id_is_not_found(self):
        with pytest.raises(CaseDocumentError, match='not found: nope'):
            render_case_documents(DOMAIN, ['nope'], USER)

    def test_missing_variable_fails_with_the_case_id(self):
        case = self._case(document_template_slug='welcome')
        with pytest.raises(CaseDocumentError, match=f'{case.case_id}.*first_name'):
            self._build(case)

    def test_case_owned_by_someone_else_is_not_found(self):
        case = self._case(document_template_slug='welcome', first_name='Alice', owner_id='someone-else')
        with pytest.raises(CaseDocumentError, match=f'not found: {case.case_id}'):
            self._build(case)

    def test_one_inaccessible_case_fails_the_request(self):
        mine = self._case(document_template_slug='welcome', first_name='Alice')
        theirs = self._case(document_template_slug='welcome', first_name='Bob', owner_id='someone-else')
        with pytest.raises(CaseDocumentError, match=theirs.case_id) as error:
            self._build(mine, theirs)
        assert mine.case_id not in str(error.value)

    def test_case_owned_by_one_of_the_users_groups_is_rendered(self):
        case = self._case(document_template_slug='welcome', first_name='Alice', owner_id=GROUP_ID)
        user = SimpleNamespace(get_owner_ids=lambda domain: ['another-user', GROUP_ID])
        assert self._build(case, user=user).startswith(b'%PDF')

    def test_closed_case_is_not_found(self):
        case = self._case(document_template_slug='welcome', first_name='Alice', closed=True)
        with pytest.raises(CaseDocumentError, match=f'not found: {case.case_id}'):
            self._build(case)
