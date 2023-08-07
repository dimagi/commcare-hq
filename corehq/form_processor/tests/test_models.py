from unittest.mock import MagicMock
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from nose.tools import assert_equal

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.models import Attachment, CommCareCase, CommCareCaseIndex

DOMAIN = 'test-domain'


class AttachmentHasSizeTests(SimpleTestCase):
    def test_handles_no_size_property(self):
        raw_content = MagicMock(spec_set=[''])
        attachment = self.create_attachment_with_content(raw_content)
        self.assertFalse(attachment.has_size())

    def test_handles_None(self):
        raw_content = MagicMock(size=None, spec_set=['size'])
        attachment = self.create_attachment_with_content(raw_content)
        self.assertFalse(attachment.has_size())

    def test_handles_valid_size(self):
        raw_content = MagicMock(size=1024, spec_set=['size'])
        attachment = self.create_attachment_with_content(raw_content)
        self.assertTrue(attachment.has_size())

    @staticmethod
    def create_attachment_with_content(content):
        return Attachment(name='test_attachment', raw_content=content, content_type='text')


class CommCareCaseTests(SimpleTestCase):
    def test_sets_index(self):
        data = {
            'indices': [{
                'referenced_id': 'some_id'
            }]
        }
        case = CommCareCase(**data)
        index = case.indices[0]
        self.assertEqual(index.referenced_id, 'some_id')

    def test_sets_index_with_doc_type(self):
        data = {
            'indices': [{
                'doc_type': 'CommCareCaseIndex',
                'referenced_id': 'some_id'
            }]
        }
        case = CommCareCase(**data)
        index = case.indices[0]
        self.assertEqual(index.referenced_id, 'some_id')


class CommCareCaseIndexTests(SimpleTestCase):
    def test_fields(self):
        data = {
            'identifier': 'my_parent',
            'relationship': 'child',
            'referenced_type': 'some_type',
            'referenced_id': 'some_id'
        }
        index = CommCareCaseIndex(**data)

        self.assertEqual(index.identifier, 'my_parent')
        self.assertEqual(index.relationship, 'child')
        self.assertEqual(index.referenced_type, 'some_type')
        self.assertEqual(index.referenced_id, 'some_id')

    def test_relationship_id_is_set_by_relationship(self):
        index = CommCareCaseIndex(relationship='extension')
        self.assertEqual(index.relationship_id, 2)

    def test_constructor_ignores_doc_type(self):
        # Just ensure it doesn't raise an exception
        data = {
            'doc_type': 'CommCareCaseIndex',
            'identifier': 'my_parent',
            'relationship': 'child',
            'referenced_type': 'comunidad',
            'referenced_id': 'ed285193-3795-4b39-b08b-ac9ad941527f'
        }
        CommCareCaseIndex(**data)


class TestIndices(TestCase):
    """
    Verify that when two indices are created with the same identifier,
    CommCareCase.indices returns only the last one created.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.factory = CaseFactory(domain=DOMAIN)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        johnny_id = str(uuid4())
        nathaniel_id = str(uuid4())
        elizabeth_id = str(uuid4())
        (self.johnny_case,
         self.nathaniel_case,
         self.elizabeth_case) = self.factory.create_or_update_case(
            CaseStructure(
                case_id=johnny_id,
                attrs={
                    'create': True,
                    'case_type': 'child',
                    'case_name': 'Johnny APPLESEED',
                    'owner_id': 'b0b',
                    'external_id': 'johnny12345',
                    'update': {
                        'first_name': 'Johnny',
                        'last_name': 'Appleseed',
                        'date_of_birth': '2021-08-27',
                        'dhis2_org_unit_id': 'abcdef12345',
                    },
                },
                indices=[
                    CaseIndex(
                        CaseStructure(
                            case_id=nathaniel_id,
                            attrs={
                                'create': True,
                                'case_type': 'parent',
                                'case_name': 'Nathaniel CHAPMAN',
                                'owner_id': 'b0b',
                                'external_id': 'nathaniel12',
                                'update': {
                                    'first_name': 'Nathaniel',
                                    'last_name': 'Chapman',
                                    'dhis2_org_unit_id': 'abcdef12345',
                                },
                            },
                        ),
                        relationship='child',
                        related_type='parent',
                        identifier='parent',
                    ),
                    CaseIndex(
                        CaseStructure(
                            case_id=elizabeth_id,
                            attrs={
                                'create': True,
                                'case_type': 'parent',
                                'case_name': 'Elizabeth SIMONDS',
                                'owner_id': 'b0b',
                                'external_id': 'elizabeth12',
                                'update': {
                                    'first_name': 'Elizabeth',
                                    'last_name': 'Simonds',
                                    'dhis2_org_unit_id': 'abcdef12345',
                                },
                            },
                        ),
                        relationship='child',
                        related_type='parent',
                        identifier='parent',
                    )
                ],
            )
        )

    def test_case_indices(self):
        indices = self.johnny_case.indices
        self.assertEqual(len(indices), 1)
        case = CommCareCase.objects.get_case(indices[0].referenced_id, DOMAIN)
        self.assertTrue(are_cases_equal(case, self.elizabeth_case))


def are_cases_equal(a, b):  # or at least equal enough for our test
    attrs = ('domain', 'case_id', 'type', 'name', 'owner_id')
    return all(getattr(a, attr) == getattr(b, attr) for attr in attrs)


def test_case_to_json():
    case_id = str(uuid4())
    case = CommCareCase(
        case_id=case_id,
        domain=DOMAIN,
        type='case',
        name='Justin Case',
        case_json={
            'given_name': 'Justin',
            'family_name': 'Case',
            'actions': 'eating sleeping typing',
            'indices': 'Dow_Jones_Industrial_Average S&P_500',
        },
        indices=[
            dict(
                case_id=case_id,
                domain='healsec',
                identifier='host',
                referenced_type='person',
                referenced_id='abc123',
                relationship_id=CommCareCaseIndex.EXTENSION,
            )
        ]
    )
    case_dict = case.to_json()
    assert_equal(case_dict, {
        '_id': case_id,
        'actions': [],  # Not replaced by case_json
        'backend_id': 'sql',
        'case_attachments': {},
        'case_id': case_id,
        'case_json': {
            'actions': 'eating sleeping typing',
            'family_name': 'Case',
            'given_name': 'Justin',
            'indices': 'Dow_Jones_Industrial_Average S&P_500',
        },
        'closed': False,
        'closed_by': None,
        'closed_on': None,
        'deleted': False,
        'doc_type': 'CommCareCase',
        'domain': DOMAIN,
        'external_id': None,
        'family_name': 'Case',
        'given_name': 'Justin',
        'indices': [
            {
                'case_id': case_id,
                'identifier': 'host',
                'referenced_type': 'person',
                'referenced_id': 'abc123',
                'relationship': 'extension',
            },
        ],  # Not replaced by case_json
        'location_id': None,
        'modified_by': '',
        'modified_on': None,
        'name': 'Justin Case',
        'opened_by': None,
        'opened_on': None,
        'owner_id': '',
        'server_modified_on': None,
        'type': 'case',
        'user_id': '',
        'xform_ids': [],
    })


def test_case_index_to_json():
    case_id = str(uuid4())
    index = CommCareCaseIndex(
        case_id=case_id,
        domain='healsec',
        identifier='host',
        referenced_type='person',
        referenced_id='abc123',
        relationship_id=CommCareCaseIndex.EXTENSION,
    )
    index_dict = index.to_json()
    assert_equal(index_dict, {
        'case_id': case_id,
        'identifier': 'host',
        'referenced_type': 'person',
        'referenced_id': 'abc123',
        'relationship': 'extension',
    })
