from custom.icds.location_rationalization.const import (
    EXTRACT_OPERATION,
    MERGE_OPERATION,
    MOVE_OPERATION,
    SPLIT_OPERATION,
)
from custom.icds.location_rationalization.tests.base import BaseTest


class TestParser(BaseTest):
    def test_parse(self):
        self.maxDiff = None
        transitions, errors = self.get_transitions()
        self.assertEqual(
            transitions,
            {
                'awc': {
                    MERGE_OPERATION: {'11114': ['11111', '11112', '11113']},
                    SPLIT_OPERATION: {'12211': ['12111', '12121']},
                    MOVE_OPERATION: {'11211': '11311', '11212': '11312', '11221': '11321'},
                    EXTRACT_OPERATION: {'11131': '11122'}
                },
                'supervisor': {
                    MERGE_OPERATION: {},
                    SPLIT_OPERATION: {'1221': ['1211', '1212']},
                    MOVE_OPERATION: {'1121': '1131', '1122': '1132'},
                    EXTRACT_OPERATION: {}
                },
                'block': {
                    MERGE_OPERATION: {},
                    SPLIT_OPERATION: {},
                    MOVE_OPERATION: {'112': '113'},
                    EXTRACT_OPERATION: {}
                },
                'district': {
                    MERGE_OPERATION: {},
                    SPLIT_OPERATION: {},
                    MOVE_OPERATION: {},
                    EXTRACT_OPERATION: {}
                },
                'state': {
                    MERGE_OPERATION: {},
                    SPLIT_OPERATION: {},
                    MOVE_OPERATION: {},
                    EXTRACT_OPERATION: {}
                },
            }
        )

    def test_errors(self):
        transitions, errors = self.get_errors()
        self.assertEqual(
            errors,
            ['Multiple transitions for 11114, Merge and Rename',
             'Multiple transitions for 11111, Merge and Rename',
             'Invalid Operation Unknown',
             'Multiple transitions for 11311, Extract and Rename',
             'Multiple transitions for 12211, Split and Rename',
             'Multiple transitions for 12121, Split and Rename',
             'Multiple transitions for 1221, Split and Rename',
             'Multiple transitions for 1212, Split and Rename',
             "Missing location code for Rename, got old: '12212' and new: ''"]
        )
