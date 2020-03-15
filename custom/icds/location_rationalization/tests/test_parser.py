from custom.icds.location_rationalization.const import (
    EXTRACT_TRANSITION,
    MERGE_TRANSITION,
    MOVE_TRANSITION,
    SPLIT_TRANSITION,
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
                    MERGE_TRANSITION: {'11114': ['11111', '11112', '11113']},
                    SPLIT_TRANSITION: {'12211': ['12111', '12121']},
                    MOVE_TRANSITION: {'11211': '11311', '11212': '11312', '11221': '11321'},
                    EXTRACT_TRANSITION: {'11131': '11122'}
                },
                'supervisor': {
                    MERGE_TRANSITION: {},
                    SPLIT_TRANSITION: {'1221': ['1211', '1212']},
                    MOVE_TRANSITION: {'1121': '1131', '1122': '1132'},
                    EXTRACT_TRANSITION: {}
                },
                'block': {
                    MERGE_TRANSITION: {},
                    SPLIT_TRANSITION: {},
                    MOVE_TRANSITION: {'112': '113'},
                    EXTRACT_TRANSITION: {}
                },
                'district': {
                    MERGE_TRANSITION: {},
                    SPLIT_TRANSITION: {},
                    MOVE_TRANSITION: {},
                    EXTRACT_TRANSITION: {}
                },
                'state': {
                    MERGE_TRANSITION: {},
                    SPLIT_TRANSITION: {},
                    MOVE_TRANSITION: {},
                    EXTRACT_TRANSITION: {}
                },
            }
        )

    def test_errors(self):
        transitions, errors = self.get_errors()
        self.assertEqual(
            errors,
            ['Multiple transitions for 11114, Merge and Rename',
             'Multiple transitions for 11111, Merge and Rename',
             'Invalid Transition Unknown',
             'Multiple transitions for 11311, Extract and Rename',
             'Multiple transitions for 12211, Split and Rename',
             'Multiple transitions for 12121, Split and Rename',
             'Multiple transitions for 1221, Split and Rename',
             'Multiple transitions for 1212, Split and Rename']
        )
