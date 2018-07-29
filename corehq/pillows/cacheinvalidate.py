from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.cache.cache_core import GenerationCache
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.feed.couch import CouchChangeFeed
from pillowtop.models import DjangoPillowCheckpoint
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor

pillow_logging = logging.getLogger("pillowtop")


class FakeCheckpoint(PillowCheckpoint):
    def __init__(self, checkpoint_id, couch_db):
        super(FakeCheckpoint, self).__init__("{}_{}".format(checkpoint_id, couch_db.dbname), 'text')
        self.couch_db = couch_db

    def get_or_create_wrapped(self, verify_unchanged=False):
        return DjangoPillowCheckpoint(
            checkpoint_id=self.checkpoint_id,
            sequence=self.couch_db.info()['update_seq'],
        )

    def get_current_sequence_id(self):
        return self.couch_db.info()['update_seq']

    def update_to(self, seq):
        pass

    def reset(self):
        pass

    def touch(self, min_interval):
        pass


class CacheInvalidateProcessor(PillowProcessor):
    def __init__(self):
        self.gen_caches = set(GenerationCache.doc_type_generation_map().values())

    def get_generations(self):
        return ["%s :: %s" % (gc.generation_key, gc._get_generation()) for gc in self.gen_caches]

    def process_change(self, pillow_instance, change):
        self.process_doc(change.get_document(), change.deleted)

    def process_doc(self, doc, is_deleted):
        """
        This function does actual cache invalidation. It's also called manually
        by directly invalidated things.
        """
        doc_id = doc['_id']
        if doc_id.startswith('pillowtop_corehq.pillows'):
            return None

        # send document to cache invalidation workflow
        generations_prior = set(self.get_generations())
        cache_core.invalidate_doc(doc, deleted=is_deleted)
        generations_after = set(self.get_generations())

        generation_change = generations_prior.symmetric_difference(generations_after)
        if len(generation_change) > 0:
            pillow_logging.debug("[CacheInvalidate]: Change %s (%s), generation change: %s" % (
                doc_id, doc.get('doc_type', 'unknown'), ', '.join(generation_change))
            )
        else:
            pillow_logging.debug(
                "[CacheInvalidate]: Change %s (%s), no generation change" % (
                    doc_id, doc.get('doc_type', 'unknown')
                )
            )


def get_main_cache_invalidation_pillow(pillow_id, **kwargs):
    from couchforms.models import XFormInstance
    return _get_cache_invalidation_pillow(pillow_id, XFormInstance.get_db(), couch_filter="hqadmin/not_case_form")


def get_user_groups_cache_invalidation_pillow(pillow_id, **kwargs):
    from corehq.apps.users.models import CommCareUser
    return _get_cache_invalidation_pillow(pillow_id, CommCareUser.get_db())


def _get_cache_invalidation_pillow(pillow_id, couch_db, couch_filter=None):
    """
    Pillow that listens to changes and invalidates the cache whether it's a
    a single doc being cached, to a view.
    """
    checkpoint = FakeCheckpoint(
        'cache_invalidate_pillow', couch_db
    )
    change_feed = CouchChangeFeed(couch_db, couch_filter=couch_filter)
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=CacheInvalidateProcessor(),
    )
