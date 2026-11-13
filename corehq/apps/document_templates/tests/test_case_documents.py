import uuid
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from PIL import Image

from corehq.apps.document_templates.case_documents import (
    MAX_CASES,
    CaseDocumentError,
    Failure,
    render_case_documents,
)
from corehq.apps.document_templates.images import save_image
from corehq.apps.document_templates.models import Area, Template
from corehq.apps.document_templates.rendering import generate_document
from corehq.apps.hqmedia.models import CommCareImage
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
        with pytest.raises(CaseDocumentError, match='No cases') as error:
            render_case_documents(DOMAIN, [], USER)
        assert error.value.failures == []

    def test_too_many_cases_is_an_error(self):
        with pytest.raises(CaseDocumentError, match=f'At most {MAX_CASES}') as error:
            render_case_documents(DOMAIN, [f'case-{i}' for i in range(MAX_CASES + 1)], USER)
        assert error.value.failures == []


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

    def _case(self, domain=DOMAIN, owner_id=OWNER_ID, closed=False, name='', **case_json):
        return create_case(
            domain, save=True, case_type='patient', owner_id=owner_id, closed=closed, name=name,
            case_json=case_json,
        )

    def _build(self, *cases, domain=DOMAIN, user=USER):
        return render_case_documents(domain, [case.case_id for case in cases], user)

    def _failures(self, *cases, **kwargs):
        with pytest.raises(CaseDocumentError) as error:
            self._build(*cases, **kwargs)
        return error.value.failures

    def _failure(self, *cases, **kwargs):
        [failure] = self._failures(*cases, **kwargs)
        return failure

    def test_each_case_is_rendered_with_its_own_properties_in_order(self):
        alice = self._case(document_template_slug='welcome', first_name='Alice')
        bob = self._case(document_template_slug='welcome', first_name='Bob')
        with patch(
            'corehq.apps.document_templates.case_documents.generate_document', wraps=generate_document,
        ) as generate:
            pdf = self._build(bob, alice)
        assert [call.args[1]['first_name'] for call in generate.call_args_list] == ['Bob', 'Alice']
        assert pdf.startswith(b'%PDF')

    def _image_template(self, domain=DOMAIN):
        buffer = BytesIO()
        Image.new('RGB', (10, 20), color=tuple(uuid.uuid4().bytes[:3])).save(buffer, format='PNG')
        image_id = save_image(domain, SimpleUploadedFile('logo.png', buffer.getvalue()), 'user')
        self.addCleanup(CommCareImage.get(image_id).delete)
        return Template.objects.create(
            domain=DOMAIN, name='Logo', slug='logo',
            areas={'header': Area(type='image', value=image_id), 'body': Area(value='Hello')},
        )

    def test_image_areas_are_drawn(self):
        self._image_template()
        case = self._case(document_template_slug='logo')
        pdf = self._build(case)
        assert b'/Subtype /Image' in pdf

    def test_image_of_another_domain_fails_with_the_case_id(self):
        self._image_template(domain=OTHER_DOMAIN)
        case = self._case(document_template_slug='logo')
        failure = self._failure(case)
        assert failure.case_id == case.case_id
        assert 'header' in failure.reason and 'does not exist' in failure.reason

    def test_repeated_case_ids_are_rendered_once(self):
        alice = self._case(document_template_slug='welcome', first_name='Alice')
        with patch(
            'corehq.apps.document_templates.case_documents.generate_document', wraps=generate_document,
        ) as generate:
            self._build(alice, alice)
        assert generate.call_count == 1

    def test_case_without_a_slug_fails_the_request(self):
        good = self._case(document_template_slug='welcome', first_name='Alice')
        bad = self._case(first_name='Bob', name='Bob')
        assert self._failures(good, bad) == [Failure(bad.case_id, 'Bob', 'No known "document_template_slug"')]

    def test_unknown_slug_fails_the_request(self):
        case = self._case(document_template_slug='nope', first_name='Alice')
        assert self._failure(case).case_id == case.case_id

    def test_template_of_another_domain_is_not_used(self):
        case = self._case(document_template_slug='theirs')
        assert self._failure(case).case_id == case.case_id

    def test_deleted_template_is_not_used(self):
        Template.objects.create(domain=DOMAIN, name='Retired', slug='retired', areas={}, deleted=True)
        case = self._case(document_template_slug='retired')
        assert self._failure(case).case_id == case.case_id

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
        case = self._case(domain=OTHER_DOMAIN, document_template_slug='theirs', name='Theirs')
        assert self._failure(case) == Failure(case.case_id, '', 'Case not found')

    def test_unknown_case_id_is_not_found(self):
        with pytest.raises(CaseDocumentError) as error:
            render_case_documents(DOMAIN, ['nope'], USER)
        assert error.value.failures == [Failure('nope', '', 'Case not found')]

    def test_missing_variable_fails_with_the_case_id(self):
        case = self._case(document_template_slug='welcome', name='Alice')
        assert self._failure(case) == Failure(case.case_id, 'Alice', "body: 'first_name' is undefined")

    def test_case_owned_by_someone_else_is_not_found(self):
        case = self._case(
            document_template_slug='welcome', first_name='Alice', owner_id='someone-else', name='Alice',
        )
        assert self._failure(case) == Failure(case.case_id, '', 'Case not found')

    def test_one_inaccessible_case_fails_the_request(self):
        mine = self._case(document_template_slug='welcome', first_name='Alice')
        theirs = self._case(document_template_slug='welcome', first_name='Bob', owner_id='someone-else')
        assert [failure.case_id for failure in self._failures(mine, theirs)] == [theirs.case_id]

    def test_case_owned_by_one_of_the_users_groups_is_rendered(self):
        case = self._case(document_template_slug='welcome', first_name='Alice', owner_id=GROUP_ID)
        user = SimpleNamespace(get_owner_ids=lambda domain: ['another-user', GROUP_ID])
        pdf = self._build(case, user=user)
        assert pdf.startswith(b'%PDF')

    def test_closed_case_is_not_found(self):
        case = self._case(document_template_slug='welcome', first_name='Alice', closed=True)
        assert self._failure(case) == Failure(case.case_id, '', 'Case not found')

    def _mixed_cases(self):
        Template.objects.create(
            domain=DOMAIN, name='Long address', slug='long-address',
            areas={'address': Area(value='\n\n'.join(['line'] * 50)), 'body': Area(value='Hello')},
        )
        return [
            self._case(document_template_slug='welcome', first_name='Alice', name='Alice'),
            SimpleNamespace(case_id='missing'),
            self._case(document_template_slug='nope', name='Bob'),
            self._case(document_template_slug='welcome', name='Carol'),
            self._case(document_template_slug='long-address', name='Dan'),
            self._case(document_template_slug='welcome', first_name='Eve', name='Eve'),
        ]

    def test_every_failure_is_reported_in_one_request(self):
        alice, missing, bob, carol, dan, eve = self._mixed_cases()
        with pytest.raises(CaseDocumentError, match='4 of 6 cases cannot be rendered') as error:
            self._build(alice, missing, bob, carol, dan, eve)
        assert error.value.failures == [
            Failure('missing', '', 'Case not found'),
            Failure(bob.case_id, 'Bob', 'No known "document_template_slug"'),
            Failure(carol.case_id, 'Carol', "body: 'first_name' is undefined"),
            Failure(dan.case_id, 'Dan', 'address does not fit its area'),
        ]
