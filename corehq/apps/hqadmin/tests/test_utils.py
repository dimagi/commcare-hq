from __future__ import absolute_import
from django.test import TestCase, override_settings, SimpleTestCase

from corehq.apps.hqadmin.utils import check_for_rewind
from corehq.util.test_utils import generate_cases
from pillowtop import get_all_pillow_instances
from testapps.test_pillowtop.utils import real_pillow_settings
from ..models import HistoricalPillowCheckpoint
from ..utils import EPSILON, parse_celery_workers, parse_celery_pings


def _get_dummy_pillow():
    from pillowtop.tests.utils import make_fake_constructed_pillow
    return make_fake_constructed_pillow('dummy pillow', 'test_checkpoint_seq_store')

DummyPillow = _get_dummy_pillow


@override_settings(PILLOWTOPS={'test': ['corehq.apps.hqadmin.tests.test_utils.DummyPillow']})
class TestPillowCheckpointSeqStore(TestCase):

    def setUp(self):
        super(TestPillowCheckpointSeqStore, self).setUp()
        self.pillow = DummyPillow()

    def tearDown(self):
        super(TestPillowCheckpointSeqStore, self).tearDown()

    def test_basic_cloudant_seq(self):
        seq = '1-blahblah'
        self.pillow.set_checkpoint({'seq': seq})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)
        store = HistoricalPillowCheckpoint.get_latest(self.pillow.checkpoint.checkpoint_id)
        self.assertEquals(store.seq, seq)

    def test_basic_couchdb_seq(self):
        seq = 100
        self.pillow.set_checkpoint({'seq': seq})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)
        store = HistoricalPillowCheckpoint.get_latest(self.pillow.checkpoint.checkpoint_id)
        self.assertEquals(store.seq, str(seq))

    def test_small_rewind(self):
        """
        We should not notify if the seq is not significantly less than the previous
        """
        seq = '10-blahblah'
        self.pillow.set_checkpoint({'seq': seq})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)

        seq_rewind = '9-blahblah'
        self.pillow.set_checkpoint({'seq': seq_rewind})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)

        has_rewound, historical_seq = check_for_rewind(self.pillow.checkpoint)
        self.assertFalse(has_rewound)
        self.assertEqual(historical_seq, seq)

    def test_large_rewind(self):
        """
        We should notify if the seq is significantly less than the previous and not update the seq
        """
        seq = '{}-blahblah'.format(EPSILON + 10)
        self.pillow.set_checkpoint({'seq': seq})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)

        seq_rewind = '9-blahblah'
        self.pillow.set_checkpoint({'seq': seq_rewind})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)

        has_rewound, historical_seq = check_for_rewind(self.pillow.checkpoint)
        self.assertTrue(has_rewound)
        self.assertEqual(historical_seq, seq)

    def test_get_latest_for_pillow(self):
        seq = '10-blahblah'
        self.pillow.set_checkpoint({'seq': seq})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)

        store = HistoricalPillowCheckpoint.get_latest_for_pillow('DummyPillow')
        self.assertIsNotNone(store)

        store = HistoricalPillowCheckpoint.get_latest_for_pillow('DummyPillowThatDoesNotExist')
        self.assertIsNone(store)

    def test_get_historical_max(self):
        seq0 = '12-blahblah'
        self.pillow.set_checkpoint({'seq': seq0})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)

        seq1 = '10-blahblah'
        self.pillow.set_checkpoint({'seq': seq1})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)

        seq2 = '2-blahblah'
        self.pillow.set_checkpoint({'seq': seq2})
        HistoricalPillowCheckpoint.create_checkpoint_snapshot(self.pillow.checkpoint)

        store = HistoricalPillowCheckpoint.get_historical_max(self.pillow.checkpoint.checkpoint_id)
        self.assertIsNotNone(store)
        self.assertEqual(store.seq, seq0)

        store = HistoricalPillowCheckpoint.get_historical_max('CheckpointThatDoesNotExist')
        self.assertIsNone(store)


class TestHistoricalPillowCheckpoint(TestCase):

    @real_pillow_settings()
    def test_all_pillows(self):
        for pillow in get_all_pillow_instances():
            checkpoint = pillow.checkpoint
            current_seq = checkpoint.get_current_sequence_id()
            HistoricalPillowCheckpoint.create_checkpoint_snapshot(checkpoint)
            latest = HistoricalPillowCheckpoint.get_latest(checkpoint.checkpoint_id)
            checkpoint.reset()
            checkpoint.update_to(latest.seq)
            self.assertEqual(checkpoint.get_current_sequence_id(), current_seq)


class TestParseCeleryWorkerPings(SimpleTestCase):
    """
    Ensures that we correctly response the celery ping responses
    """
    def test_celery_worker_pings(self):
        response = parse_celery_pings([
            {'celery@myhost': {'ok': 'pong'}},
            {'celery@otherhost': {'ok': 'pong'}},
            {'celery@yikes': {'ok': 'notpong'}},
        ])
        self.assertEqual(response, {
            'celery@myhost': True,
            'celery@otherhost': True,
            'celery@yikes': False,
        })

    def test_celery_worker_pings_empty(self):
        response = parse_celery_pings([])

        self.assertEqual(response, {})


class TestParseCeleryWorkers(SimpleTestCase):
    """
    Ensures that we parse the hosts returned from flower into
    workers we expect to be running and workers we don't.
    """


@generate_cases([
    # Ensures we correctly parse a single regular worker
    ({'regular_host': True}, (['regular_host'], [])),
    # Ensures we correctly parse a single timestamped worker
    ({'main_.20_timestamp': True}, (['main_.20_timestamp'], [])),
    # Ensures we parse timestamped and regular
    ({
        'main_.40_timestamp': True,
        'regular_host': True,
    }, (['regular_host', 'main_.40_timestamp'], [])),
    # Ensures we correctly parse multiple timestamped workers
    ({
        'main_.40_timestamp': True,
        'main_.20_timestamp': True,
        'main_.30_timestamp': True,
    }, (['main_.40_timestamp'], ['main_.30_timestamp', 'main_.20_timestamp'])),

    # Ensures we correctly parse multiple timestamped workers
    ({
        'main_.40_timestamp': True,
        'main_.20_timestamp': True,
        'main_.30_timestamp': True,
        'secondary_.30_timestamp': True,
        'secondary_.20_timestamp': True,
    }, (
        ['main_.40_timestamp', 'secondary_.30_timestamp'],
        ['main_.30_timestamp', 'main_.20_timestamp', 'secondary_.20_timestamp'],
    )),

], TestParseCeleryWorkers)
def test_parse_celery_workers(self, workers, expected):
    self.assertEqual(parse_celery_workers(workers), expected)
