from casexml.apps.case.xml.parser import CaseUpdate
from casexml.apps.case.xml import V2
from django.test import SimpleTestCase


class CaseUpdateTests(SimpleTestCase):
    def test_constructor(self):
        create_block = {
            'case_name': 'test_case',
            'owner_id': '12345',
            'case_type': 'test_case_type'
        }
        update_block = {
            'email': 'test@email.com'
        }
        case_block = self._create_case_block(create_block, update_block)

        case_update = CaseUpdate('case_id', V2, case_block)

        self.assertEqual(case_update.id, 'case_id')
        self.assertEqual(case_update.version, V2)
        self.assertEqual(case_update.user_id, '')
        self.assertEqual(case_update.modified_on_str, '')

        self.assertTrue(case_update.creates_case())
        self.assertTrue(case_update.updates_case())
        self.assertEqual(case_update.create_block['case_name'], 'test_case')
        self.assertEqual(case_update.update_block['email'], 'test@email.com')

    def test_get_normalized_updates(self):
        create_block = {
            'case_name': 'test_case',
            'owner_id': '12345',
            'case_type': 'test_case_type'
        }
        case_block = self._create_case_block(create_block)

        case_update = CaseUpdate('case_id', V2, case_block)

        self.assertEqual(case_update.get_normalized_update_property_names(),
                         {'name', 'owner_id', 'type'})

    def _create_case_block(self, create_block=None, update_block=None):
        block = {
            '@case_id': '1111',
            '@date_modified': '2023-02-09T17:01:15.054000Z',
            '@user_id': '2222',
            '@xmlns': 'http://commcarehq.org/case/transaction/v2',
        }

        if create_block:
            block['create'] = create_block

        if update_block:
            block['update'] = update_block

        return block
