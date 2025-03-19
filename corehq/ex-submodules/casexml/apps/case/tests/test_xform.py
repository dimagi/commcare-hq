from django.test import SimpleTestCase
from casexml.apps.case.xml import V2
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml.parser import CaseUpdate


class TestGetCaseUpdates(SimpleTestCase):
    default_case_id = '1111'
    default_user_id = '2222'
    default_modified_time = '2023-11-28T15:26:55.859000Z'

    def test_processes_single_case(self):
        case_block = self._create_case_block(
            case_id='case1',
            user_id='abc',
            modified_on='2023-11-28T15:26:55.859000Z',
            create_block={'case_name': 'test', 'case_type': 'test_type'}
        )
        xform = {
            'case': case_block
        }

        updates = get_case_updates(xform)
        expected_case = self._create_case_update(
            case_id='case1',
            user_id='abc',
            modified_on='2023-11-28T15:26:55.859000Z',
            create_block={'case_name': 'test', 'case_type': 'test_type'}
        )
        self.assertEqual(expected_case, updates[0])

    def test_processes_sub_case(self):
        case1 = self._create_case_block(case_id='1')
        case2 = self._create_case_block(case_id='2')
        xform = {
            'case': case1,
            'sub_case': {
                'case': case2
            }
        }

        updates = get_case_updates(xform)
        self.assertEqual(updates, [self._create_case_update(case_id='1'), self._create_case_update(case_id='2')])

    def test_can_restrict_by_id(self):
        case1 = self._create_case_block(case_id='1')
        case2 = self._create_case_block(case_id='2')
        xform = {
            'case': case1,
            'sub_case': {
                'case': case2
            }
        }

        updates = get_case_updates(xform, for_case='1')
        self.assertEqual(updates, [self._create_case_update(case_id='1')])

    def _create_case_block(
            self, case_id=None, user_id=None, modified_on=None, create_block=None, update_block=None):
        block = {
            '@case_id': case_id or self.default_case_id,
            '@date_modified': modified_on or self.default_modified_time,
            '@user_id': user_id or self.default_user_id,
            '@xmlns': 'http://commcarehq.org/case/transaction/v2',
        }

        if create_block:
            block['create'] = create_block

        if update_block:
            block['update'] = update_block

        return block

    def _create_case_update(
            self, case_id=None, user_id=None, modified_on=None, create_block=None, update_block=None):
        block = self._create_case_block(case_id, user_id, modified_on, create_block, update_block)

        return CaseUpdate(
            case_id or self.default_case_id, V2, block,
            user_id=(user_id or self.default_user_id),
            modified_on_str=modified_on or self.default_modified_time)
