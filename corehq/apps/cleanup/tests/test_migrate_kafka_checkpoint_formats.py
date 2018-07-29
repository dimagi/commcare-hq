from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple

from django.test.testcases import SimpleTestCase

from corehq.apps.cleanup.pillow_migrations import migrate_kafka_sequence
from corehq.util.test_utils import generate_cases
from pillowtop.models import DjangoPillowCheckpoint


FakeFeed = namedtuple('FakeFeed', 'topics')


class TestMigrateSequence(SimpleTestCase):
    pass


@generate_cases([
    ('text', FakeFeed(['t1']), "123", '{"t1,0": 123}'),
    ('json', FakeFeed(['t1']), "123", '{"t1,0": 123}'),
    ('text', FakeFeed(['t1', 't2']), "123", None, AssertionError),
    ('json', FakeFeed(['t1', 't2']), "123", None, AssertionError),
    ('json', FakeFeed(['t1', 't2']), "abc", None, ValueError),
    ('json', FakeFeed(['t1', 't2']), '{"t1": 123, "t2": 345}', '{"t1,0": 123, "t2,0": 345}'),
], TestMigrateSequence)
def test_migate_sequence(self, format, feed, old_seq, new_seq, error=None):
    checkpoint = DjangoPillowCheckpoint(sequence=old_seq, sequence_format=format)
    if error:
        with self.assertRaises(error):
            migrate_kafka_sequence(feed, checkpoint)
    else:
        migrated = migrate_kafka_sequence(feed, checkpoint)
        self.assertEqual(new_seq, migrated)
