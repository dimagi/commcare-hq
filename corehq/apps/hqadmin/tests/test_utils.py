from django.test import TestCase, override_settings
from pillowtop.listener import BasicPillow
from corehq.apps.domain.models import Domain

from ..utils import pillow_seq_store, EPSILON
from ..models import PillowCheckpointSeqStore


class DummyPillow(BasicPillow):
    document_class = Domain

    def run(self):
        pass


@override_settings(PILLOWTOPS={'test': ['corehq.apps.hqadmin.tests.test_utils.DummyPillow']})
class TestPillowCheckpointSeqStore(TestCase):

    def setUp(self):
        self.pillow = DummyPillow()

    def test_basic_cloudant_seq(self):
        seq = '1-blahblah'
        self.pillow.set_checkpoint({'seq': seq})
        pillow_seq_store()
        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.checkpoint_manager.checkpoint_id)
        self.assertEquals(store.seq, seq)

    def test_basic_couchdb_seq(self):
        seq = 100
        self.pillow.set_checkpoint({'seq': seq})
        pillow_seq_store()
        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.checkpoint_manager.checkpoint_id)
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

        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.checkpoint_manager.checkpoint_id)
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

        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.checkpoint_manager.checkpoint_id)
        self.assertEquals(store.seq, seq)
