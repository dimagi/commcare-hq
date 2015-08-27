from dimagi.utils.logging import notify_exception
from pillowtop.utils import get_all_pillows

from .models import PillowCheckpointSeqStore

EPSILON = 100000


def pillow_seq_store():
    for pillow in get_all_pillows():
        checkpoint = pillow.get_checkpoint()
        store, created = PillowCheckpointSeqStore.objects.get_or_create(checkpoint_id=checkpoint['_id'])
        if not created and checkpoint['seq'] < store.checkpoint_id:
            notify_exception(
                None,
                message='Found seq number lower than previous for {}. '
                        'This could mean we are in a rewid state'.format(store.checkpoint_id)
            )
        else:
            store.seq = checkpoint['seq']
            store.save()
