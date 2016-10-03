from django.test import TestCase, override_settings, SimpleTestCase
from mock import patch

from corehq.util.test_utils import generate_cases
from ..models import PillowCheckpointSeqStore
from ..utils import pillow_seq_store, EPSILON, parse_celery_workers


def _get_dummy_pillow():
    from pillowtop.tests.utils import make_fake_constructed_pillow
    return make_fake_constructed_pillow('dummy pillow', 'test_checkpoint_seq_store')

DummyPillow = _get_dummy_pillow


@override_settings(PILLOWTOPS={'test': ['corehq.apps.hqadmin.tests.test_utils.DummyPillow']})
class TestPillowCheckpointSeqStore(TestCase):

    def setUp(self):
        super(TestPillowCheckpointSeqStore, self).setUp()
        self.pillow = DummyPillow()
        self.pillow_patch = patch("corehq.apps.hqadmin.utils.get_couch_pillow_instances", return_value=[DummyPillow()])
        self.pillow_patch.start()

    def tearDown(self):
        self.pillow_patch.stop()
        super(TestPillowCheckpointSeqStore, self).tearDown()

    def test_basic_cloudant_seq(self):
        seq = '1-blahblah'
        self.pillow.set_checkpoint({'seq': seq})
        pillow_seq_store()
        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.checkpoint.checkpoint_id)
        self.assertEquals(store.seq, seq)

    def test_basic_couchdb_seq(self):
        seq = 100
        self.pillow.set_checkpoint({'seq': seq})
        pillow_seq_store()
        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.checkpoint.checkpoint_id)
        self.assertEquals(store.seq, str(seq))

    def test_small_rewind(self):
        """
        We should not notify if the seq is not significantly less than the previous
        """
        seq = '10-blahblah'
        self.pillow.set_checkpoint({'seq': seq})
        pillow_seq_store()

        seq_rewind = '9-blahblah'
        self.pillow.set_checkpoint({'seq': seq_rewind})
        pillow_seq_store()

        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.checkpoint.checkpoint_id)
        self.assertEquals(store.seq, seq_rewind)

    def test_large_rewind(self):
        """
        We should notify if the seq is significantly less than the previous and not update the seq
        """
        seq = '{}-blahblah'.format(EPSILON + 10)
        self.pillow.set_checkpoint({'seq': seq})
        pillow_seq_store()

        seq_rewind = '9-blahblah'
        self.pillow.set_checkpoint({'seq': seq_rewind})
        pillow_seq_store()

        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.checkpoint.checkpoint_id)
        self.assertEquals(store.seq, seq)

    def test_get_by_pillow_name(self):
        seq = '10-blahblah'
        self.pillow.set_checkpoint({'seq': seq})
        pillow_seq_store()

        store = PillowCheckpointSeqStore.get_by_pillow_name('DummyPillow')
        self.assertIsNotNone(store)

        store = PillowCheckpointSeqStore.get_by_pillow_name('DummyPillowThatDoesNotExist')
        self.assertIsNone(store)


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
