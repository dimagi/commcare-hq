import doctest
from contextlib import contextmanager

from django.test import TestCase

from casexml.apps.case.const import CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase

from ..api.core import serialize_case
from ..case_helper import CaseHelper

DOMAIN = 'test-domain'


def test_doctests():
    import corehq.apps.hqcase.case_helper as module
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0


class CaseHelperTests(TestCase):

    def test_create_case_format(self):
        with get_child_case() as case:
            case_data = serialize_case(case)
            original_case_id = case_data['case_id']
            helper = CaseHelper(domain=DOMAIN)
            helper.create_case(case_data)
            self.assertIsInstance(helper.case, CommCareCase)
            self.assertNotEqual(helper.case.case_id, original_case_id)

    def test_create_child_case(self):
        with get_mother_case() as mother:
            case_data = {
                'case_name': "Hi'iaka",
                'case_type': 'child',
                'indices': {
                    'mother': {
                        'case_type': mother.type,
                        'case_id': mother.case_id,
                        'relationship': CASE_INDEX_CHILD,
                    },
                },
            }
            helper = CaseHelper(domain=DOMAIN)
            self.assertIsNone(helper.case)

            helper.create_case(case_data)
            self.assertEqual(len(helper.case.xform_ids), 1)
            self.assertIsInstance(helper.case, CommCareCase)
            self.assertEqual(helper.case.name, case_data['case_name'])
            self.assertEqual(helper.case.type, case_data['case_type'])
            self.assertEqual(helper.case.external_id, None)
            self.assertEqual(helper.case.owner_id, '')
            index = helper.case.get_index('mother')
            self.assertEqual(index.referenced_id, mother.case_id)
            self.assertEqual(index.referenced_type, mother.type)
            self.assertEqual(index.relationship, CASE_INDEX_CHILD)

    def test_update_property(self):
        with get_child_case() as case:
            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update({'properties': {
                'description': 'Goddess of the sea',
                'sidekick': 'Moela',
                'sidekick_kind': 'dog',
            }})

            self.assertEqual(len(helper.case.xform_ids), 2)
            self.assertEqual(
                helper.case.get_case_property('sidekick'),
                'Moela',
            )

    def test_update_special_property(self):
        with get_child_case() as case:
            self.assertEqual(len(case.xform_ids), 1)
            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update({
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
            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update({'indices': {
                'father': {
                    'case_type': father.type,
                    'case_id': father.case_id,
                    'relationship': 'child',
                }
            }})

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

    def test_empty_update(self):
        with get_child_case() as case:
            self.assertEqual(len(case.xform_ids), 1)
            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update({})

            self.assertEqual(len(helper.case.xform_ids), 1)

    def test_update_case_id(self):
        with get_child_case() as case:
            original_case_id = case.case_id
            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update(
                {'case_id': 'deadbeef'},
            )
            self.assertEqual(helper.case.case_id, original_case_id)

    def test_user_id(self):
        with get_child_case() as case:
            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update(
                {'case_name': 'Nāmaka'},
                user_id='c0ffee',
            )
            self.assertEqual(helper.case.user_id, 'c0ffee')
            form_data = helper.case.transactions[-1].form.form_data
            self.assertEqual(form_data['meta']['userID'], 'c0ffee')
            self.assertEqual(form_data['meta']['username'], '')

    def test_update_user_id(self):
        with get_child_case() as case:
            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update(
                {
                    'user_id': 'deadbeef',  # ignored
                    'modified_by': 'deadbeef',  # dropped by _copy_case_data()
                },
                user_id='c0ffee',
            )
            self.assertEqual(helper.case.user_id, 'c0ffee')
            form_data = helper.case.transactions[-1].form.form_data
            self.assertEqual(form_data['meta']['userID'], 'c0ffee')
            self.assertEqual(form_data['meta']['username'], '')

    def test_username(self):
        with get_child_case() as case, \
                get_commcare_user() as user:

            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update(
                {'case_name': 'Nāmaka'},
                user_id=user.user_id,
            )
            self.assertEqual(helper.case.user_id, user.user_id)
            form_data = helper.case.transactions[-1].form.form_data
            self.assertEqual(form_data['meta']['userID'], user.user_id)
            self.assertEqual(form_data['meta']['username'], user.username)

    def test_device_id(self):
        with get_child_case() as case:
            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update(
                {'case_name': 'Nāmaka'},
                device_id='CaseHelperTests',
            )
            form_data = helper.case.transactions[-1].form.form_data
            self.assertEqual(form_data['meta']['deviceID'], 'CaseHelperTests')

    def test_default_device_id(self):
        with get_child_case() as case:
            helper = CaseHelper(case=case, domain=DOMAIN)
            helper.update(
                {'case_name': 'Nāmaka'},
            )
            form_data = helper.case.transactions[-1].form.form_data
            self.assertEqual(
                form_data['meta']['deviceID'],
                'corehq.apps.hqcase.case_helper.CaseHelper',
            )

    def test_close(self):
        case_dict = {
            'case_name': 'Ku-waha-ilo',
            'case_type': 'father',
        }
        helper = CaseHelper(domain=DOMAIN)
        helper.create_case(case_dict)
        helper.close(user_id='c0ffee')

        self.assertEqual(len(helper.case.xform_ids), 2)
        self.assertTrue(helper.case.closed)
        self.assertEqual(helper.case.closed_by, 'c0ffee')

    def test_recreating_case(self):
        with get_child_case() as case:
            helper = CaseHelper(case=case, domain=DOMAIN)
            with self.assertRaises(AssertionError):
                helper.create_case({
                    'domain': DOMAIN,
                    'case_name': 'Ku-waha-ilo',
                    'case_type': 'father',
                })

    def test_closing_no_case(self):
        helper = CaseHelper(domain=DOMAIN)
        with self.assertRaises(AssertionError):
            helper.close()

    def test_copy_case_data(self):
        case_data = {
            'case_id': '38fd8d42168f496d8bf0d69eef4ae9e6',
            'case_name': 'Namaka',
            'case_type': 'child',
            'closed': False,
            'date_closed': None,
            'date_opened': '2023-04-06T17:11:12.101045Z',
            'domain': 'test-domain',
            'external_id': None,
            'indexed_on': '2023-04-06T17:11:12.162655Z',
            'indices': {
                'mother': {
                    'case_id': '27268dca9c2a45e1b55a290d67b5cb15',
                    'case_type': 'mother',
                    'relationship': 'child',
                }
            },
            'last_modified': '2023-04-06T17:11:12.101045Z',
            'owner_id': '',
            'properties': {},
            'server_last_modified': '2023-04-06T17:11:12.103245Z'
        }
        valid_data = CaseHelper._copy_case_data(case_data)

        self.assertNotEqual(id(valid_data), id(case_data))
        self.assertEqual(valid_data, {
            'case_name': 'Namaka',
            'case_type': 'child',
            'external_id': None,
            'indices': {
                'mother': {
                    'case_id': '27268dca9c2a45e1b55a290d67b5cb15',
                    'case_type': 'mother',
                    'relationship': 'child',
                }
            },
            'owner_id': '',
            'properties': {},
        })

    def test_get_user_duck_user_id(self):
        user = CaseHelper._get_user_duck('c0ffee', DOMAIN)
        self.assertEqual(user.user_id, 'c0ffee')
        self.assertEqual(user.username, '')

    def test_get_user_duck_none(self):
        user = CaseHelper._get_user_duck(None, DOMAIN)
        self.assertEqual(user.user_id, '')
        self.assertEqual(user.username, '')

    def test_get_user_duck_username(self):
        with get_commcare_user() as commcare_user:
            user = CaseHelper._get_user_duck(commcare_user.user_id, DOMAIN)
            self.assertEqual(user.user_id, commcare_user.user_id)
            self.assertEqual(user.username, commcare_user.username)


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


@contextmanager
def get_commcare_user():
    user = CommCareUser.create(
        DOMAIN, f'testy@{DOMAIN}.commcarehq.org', '******', None, None,
    )
    try:
        yield user
    finally:
        user.delete(DOMAIN, None, None)
