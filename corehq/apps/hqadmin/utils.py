from dimagi.utils.logging import notify_exception
from pillowtop.utils import force_seq_int, get_all_pillow_instances

from .models import PillowCheckpointSeqStore

EPSILON = 10000000


def pillow_seq_store():
    for pillow in get_all_pillow_instances():
        checkpoint = pillow.checkpoint
        store, created = PillowCheckpointSeqStore.objects.get_or_create(checkpoint_id=checkpoint.checkpoint_id)
        db_seq = checkpoint.get_current_sequence_id()
        store_seq = force_seq_int(store.seq) or 0
        if not created and force_seq_int(db_seq) < store_seq - EPSILON:
            notify_exception(
                None,
                message='Found seq number lower than previous for {}. '
                        'This could mean we are in a rewind state'.format(store.checkpoint_id),
                details={
                    'pillow checkpoint seq': db_seq,
                    'stored seq': store.seq
                })
        else:
            store.seq = db_seq
            store.save()
