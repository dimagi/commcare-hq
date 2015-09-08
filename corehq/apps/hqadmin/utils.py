from dimagi.utils.logging import notify_exception
from pillowtop.utils import get_all_pillows, force_seq_int

from .models import PillowCheckpointSeqStore

EPSILON = 10000000


def pillow_seq_store():
    for pillow in get_all_pillows():
        checkpoint = pillow.get_checkpoint()
        store, created = PillowCheckpointSeqStore.objects.get_or_create(checkpoint_id=checkpoint['_id'])
        if not created and force_seq_int(checkpoint['seq']) < force_seq_int(store.seq) - EPSILON:
            notify_exception(
                None,
                message='Found seq number lower than previous for {}. '
                        'This could mean we are in a rewind state'.format(store.checkpoint_id),
                details={
                    'pillow checkpoint seq': checkpoint['seq'],
                    'stored seq': store.seq
                })
        else:
            store.seq = checkpoint['seq']
            store.save()
