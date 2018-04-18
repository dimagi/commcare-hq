from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.testcases import SimpleTestCase

from corehq.apps.cleanup.pillow_migrations import get_merged_sequence
from pillowtop.models import DjangoPillowCheckpoint


class TestMergeCheckpoints(SimpleTestCase):
    def test_merge_sequence(self):
        checkpoints_topics = [
            (DjangoPillowCheckpoint(sequence=0, sequence_format='text'), 'form'),
            (DjangoPillowCheckpoint(sequence=2, sequence_format='text'), 'sql-form'),
        ]
        sequence = get_merged_sequence(checkpoints_topics)
        self.assertEqual(sequence, {
            'form': 0,
            'sql-form': 2
        })

    def test_merge_sequence_empty(self):
        sequence = get_merged_sequence([])
        self.assertEqual(sequence, {})

    def test_merge_sequence_min(self):
        checkpoints_topics = [
            (DjangoPillowCheckpoint(sequence=3, sequence_format='text'), 'form'),
            (DjangoPillowCheckpoint(sequence=0, sequence_format='text'), 'form'),
            (DjangoPillowCheckpoint(sequence=2, sequence_format='text'), 'sql-form'),
        ]
        sequence = get_merged_sequence(checkpoints_topics)
        self.assertEqual(sequence, {
            'form': 0,
            'sql-form': 2
        })

    def test_merge_sequence_mixed_format(self):
        checkpoints_topics = [
            (DjangoPillowCheckpoint(sequence=5, sequence_format='text'), 'form'),
            (DjangoPillowCheckpoint(sequence='8', sequence_format='text'), 'form'),
            (
                DjangoPillowCheckpoint(sequence='{"form": 2, "sql-form": 3}', sequence_format='json'),
                None
            ),
            (
                DjangoPillowCheckpoint(sequence='{"case": 9, "sql-case": 7}', sequence_format='json'),
                None
            ),
        ]
        sequence = get_merged_sequence(checkpoints_topics)
        self.assertEqual(sequence, {
            'form': 2,
            'sql-form': 3,
            'case': 9,
            'sql-case': 7
        })
