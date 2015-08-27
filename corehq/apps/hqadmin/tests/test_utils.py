from django.test import TestCase
from corehq.pillows.case import CasePillow

from ..utils import pillow_seq_store
from ..models import PillowCheckpointSeqStore


def import_settings():
    class MockSettings(object):
        PILLOWTOPS = {'test': ['corehq.pillows.case.CasePillow']}

    return MockSettings()


class TestPillowCheckpointSeqStore(TestCase):

    def setUp(self):
        import pillowtop.run_pillowtop
        pillowtop.utils.import_settings = import_settings
        self.pillow = CasePillow()

    def test_basic(self):
        seq = '1-blahblah'
        self.pillow.set_checkpoint({'seq': seq})
        pillow_seq_store()
        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.get_checkpoint()['_id'])
        self.assertEquals(store.seq, seq)

    def test_rewind(self):
        seq = '2-blahblah'
        self.pillow.set_checkpoint({'seq': seq})
        pillow_seq_store()

        seq_rewind = '1-blahblah'
        self.pillow.set_checkpoint({'seq': seq_rewind})
        pillow_seq_store()

        store = PillowCheckpointSeqStore.objects.get(checkpoint_id=self.pillow.get_checkpoint()['_id'])
        self.assertEquals(store.seq, seq)
