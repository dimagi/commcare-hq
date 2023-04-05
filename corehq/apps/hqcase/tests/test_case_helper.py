import doctest
from uuid import uuid4

from django.test import TestCase

from contextlib import contextmanager

from jsonschema import ValidationError
from nose.tools import assert_raises_regexp

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.form_processor.models import CommCareCase

from ..case_helper import validate_case_api_json, CaseHelper

DOMAIN = 'test-domain'


def test_doctests():
    import corehq.apps.hqcase.case_helper as module
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0


class CaseHelperTests(TestCase):

    def test_validate_good(self):
        with get_child_case() as case:
            case_api_json = case.to_api_json(lite=True)
            validate_case_api_json(case_api_json)

    def test_validate_bad(self):
        with get_child_case() as case:
            case_api_json = case.to_api_json(lite=True)
            del case_api_json['properties']['case_name']
            with assert_raises_regexp(ValidationError,
                                      "^'case_name' is a required property"):
                validate_case_api_json(case_api_json)

    def test_create_case(self):
        with get_mother_case() as mother:
            case_dict = {
                'case_id': uuid4().hex,
                'domain': DOMAIN,
                'properties': {
                    'case_name': "Hi'iaka",
                    'case_type': 'child',
                },
                'indices': {
                    'mother': {
                        'case_type': mother.type,
                        'case_id': mother.case_id,
                        'relationship': 'child',
                    },
                },
            }
            helper = CaseHelper()
            self.assertIsNone(helper.case)

            helper.create_case(case_dict)
            self.assertEqual(len(helper.case.xform_ids), 1)
            self.assertIsInstance(helper.case, CommCareCase)
            self.assertEqual(helper.case.case_id, case_dict['case_id'])
            self.assertEqual(helper.case.domain, case_dict['domain'])
            self.assertEqual(helper.case.name, case_dict['properties']['case_name'])
            self.assertEqual(helper.case.type, case_dict['properties']['case_type'])
            self.assertEqual(helper.case.external_id, None)
            self.assertEqual(helper.case.owner_id, '')
            index = helper.case.get_index('mother')
            self.assertEqual(index.referenced_id, mother.case_id)
            self.assertEqual(index.referenced_type, mother.type)
            self.assertEqual(index.relationship, 'child')

    def test_update_property(self):
        with get_child_case() as case:
            helper = CaseHelper(case)
            helper.update(properties={
                'description': 'Goddess of the sea',
                'sidekick': 'Moela',
                'sidekick_kind': 'dog',
            })

            self.assertEqual(len(helper.case.xform_ids), 2)
            self.assertEqual(
                helper.case.get_case_property('sidekick'),
                'Moela',
            )

    def test_update_special_property(self):
        with get_child_case() as case:
            self.assertEqual(len(case.xform_ids), 1)

            helper = CaseHelper(case)
            helper.update(properties={
                'case_name': 'Nāmaka',
                'external_id': '(136108) 2003 EL61 II',
            })

            self.assertEqual(len(helper.case.xform_ids), 2)
            self.assertEqual(helper.case.name, 'Nāmaka')
            self.assertEqual(helper.case.external_id, '(136108) 2003 EL61 II')

    def test_update_index(self):
        factory = CaseFactory(DOMAIN)
        father = factory.create_case(
            case_type='father',
            case_name='Ku-waha-ilo',
        )
        with get_child_case() as case:
            self.assertEqual(len(case.xform_ids), 1)

            helper = CaseHelper(case)
            helper.update(indices={
                'father': {
                    'case_type': father.type,
                    'case_id': father.case_id,
                    'relationship': 'child',
                }
            })

            self.assertEqual(len(helper.case.xform_ids), 2)
            self.assertEqual(len(helper.case.indices), 2)  # Note: index is added
            (father_idx, mother_idx) = sorted(
                helper.case.indices,
                key=lambda idx: idx.identifier
            )
            self.assertEqual(father_idx.identifier, 'father')
            self.assertEqual(father_idx.referenced_id, father.case_id)
            self.assertEqual(father_idx.referenced_type, father.type)
            self.assertEqual(father_idx.relationship, 'child')
            self.assertEqual(mother_idx.identifier, 'mother')

    def test_close(self):
        case_dict = {
            'case_id': uuid4().hex,
            'domain': DOMAIN,
            'properties': {
                'case_name': 'Ku-waha-ilo',
                'case_type': 'father',
            },
        }
        helper = CaseHelper()
        helper.create_case(case_dict)
        helper.close(user_id='c0ffee')

        self.assertEqual(len(helper.case.xform_ids), 2)
        self.assertTrue(helper.case.closed)
        self.assertEqual(helper.case.closed_by, 'c0ffee')

    def test_recreating_case(self):
        with get_child_case() as case:
            helper = CaseHelper(case)
            with self.assertRaises(AssertionError):
                helper.create_case({
                    'case_id': uuid4().hex,
                    'domain': DOMAIN,
                    'properties': {
                        'case_name': 'Ku-waha-ilo',
                        'case_type': 'father',
                    },
                })

    def test_closing_no_case(self):
        helper = CaseHelper()
        with self.assertRaises(AssertionError):
            helper.close()


@contextmanager
def get_mother_case():
    factory = CaseFactory(DOMAIN)
    mother = factory.create_case(
        case_type='mother',
        case_name='Haumea',
    )
    try:
        yield mother
    finally:
        factory.close_case(mother.case_id)


@contextmanager
def get_child_case():
    factory = CaseFactory(DOMAIN)
    with get_mother_case() as mother:
        struct = CaseStructure(
            attrs={
                'case_type': 'child',
                'case_name': 'Namaka',
                'create': True,
            },
            indices=[CaseIndex(
                relationship='child',
                identifier='mother',
                related_structure=CaseStructure(case_id=mother.case_id),
                related_type='mother',
            )],
        )
        child, __ = factory.create_or_update_cases([struct])
        try:
            yield child
        finally:
            factory.close_case(child.case_id)
