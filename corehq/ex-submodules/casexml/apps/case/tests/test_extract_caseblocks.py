import uuid
from django.test import SimpleTestCase
from casexml.apps.case.const import CASE_ATTR_ID
from casexml.apps.case.xform import extract_case_blocks


class TestExtractCaseBlocks(SimpleTestCase):

    def test_basic(self):
        block = {CASE_ATTR_ID: uuid.uuid4().hex}
        blocks = extract_case_blocks({
            'data': {
                'some': 'stuff'
            },
            'case': block
        })
        self.assertEqual(1, len(blocks))
        self.assertEqual(block, blocks[0])

    def test_simple_path(self):
        block = {CASE_ATTR_ID: uuid.uuid4().hex}
        block_with_path = extract_case_blocks({
            'data': {
                'some': 'stuff'
            },
            'case': block
        }, include_path=True)[0]
        self.assertEqual(block, block_with_path.caseblock)
        self.assertEqual([], block_with_path.path)

    def test_nested_path(self):
        block = {CASE_ATTR_ID: uuid.uuid4().hex}
        blocks = extract_case_blocks({
            'data': {
                'parents': {
                    'parent': {
                        'case': block
                    }
                }

            }
        }, include_path=True)
        self.assertEqual(1, len(blocks))
        self.assertEqual(block, blocks[0].caseblock)
        self.assertEqual(['data', 'parents', 'parent'], blocks[0].path)

    def test_blocks_in_list(self):
        blocks = [{CASE_ATTR_ID: uuid.uuid4().hex} for i in range(3)]
        blocks_back = extract_case_blocks({
            'data': {
                'parent': {
                    'parent': {
                        'case': blocks
                    }
                }

            }
        }, include_path=True)
        self.assertEqual(3, len(blocks))
        for i in range(len(blocks)):
            self.assertEqual(blocks[i], blocks_back[i].caseblock)
            self.assertEqual(['data', 'parent', 'parent'], blocks_back[i].path)

    def test_blocks_in_repeat(self):
        blocks = [{CASE_ATTR_ID: uuid.uuid4().hex} for i in range(3)]
        repeats = [{'group': {'case': block}} for block in blocks]
        blocks_back = extract_case_blocks({
            'data': {
                'parent': {
                    'repeats': repeats
                }
            }
        }, include_path=True)
        self.assertEqual(3, len(blocks))
        for i in range(len(blocks)):
            self.assertEqual(blocks[i], blocks_back[i].caseblock)
            self.assertEqual(['data', 'parent', 'repeats', 'group'], blocks_back[i].path)
