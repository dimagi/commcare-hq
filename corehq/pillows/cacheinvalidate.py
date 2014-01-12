import logging
from datetime import datetime
import simplejson

from corehq.apps.domain.models import Domain
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.cache.cache_core import GenerationCache
from pillowtop.listener import BasicPillow, ms_from_timedelta


pillow_logging = logging.getLogger("pillowtop")

class CacheInvalidatePillow(BasicPillow):
    """
    Pillow that listens to non xform/case _changes and invalidates the cache whether it's a
    a single doc being cached, to a view.
    """
    couch_filter = "hqadmin/not_case_form"  # string for filter if needed



    def __init__(self, **kwargs):
        super(CacheInvalidatePillow, self).__init__(**kwargs)
        self.couch_db = Domain.get_db()
        self.gen_caches = set(GenerationCache.doc_type_generation_map().values())

    def set_checkpoint(self, change):
        """
        Override to do nothing - don't want to cause doc update conflicts with invalidation
        """
        pass

    def reset_checkpoint(self):
        pass

    def get_checkpoint(self):
        doc_name = self.get_checkpoint_doc_name()
        current_db_seq = self.couch_db.info()['update_seq']
        checkpoint_doc = {
            "_id": doc_name,
            "seq": current_db_seq
        }
        return checkpoint_doc

    def get_generations(self):
        return ["%s :: %s" % (gc.generation_key, gc._get_generation()) for gc in self.gen_caches]

    def change_trigger(self, changes_dict):
        """
        Where all the magic happens.
        """

        #requires pillowtop to listen with include_docs
        doc = changes_dict['doc']
        doc_id = doc['_id']
        deleted = changes_dict.get('deleted', False)

        if doc_id.startswith('pillowtop_corehq.pillows'):
            return None

        #send document to cache invalidation workflow
        generations_prior = set(self.get_generations())
        existed = cache_core.invalidate_doc(doc, deleted=deleted)
        generations_after = set(self.get_generations())

        generation_change = generations_prior.symmetric_difference(generations_after)
        if len(generation_change) > 0:
            pillow_logging.info("[CacheInvalidate]: Change %s (%s), generation change: %s" % (doc_id, doc.get('doc_type', 'unknown'), ', '.join(generation_change)))
        else:
            pillow_logging.info("[CacheInvalidate]: Change %s (%s), no generation change" % (doc_id, doc.get('doc_type', 'unknown')))


    def change_transport(self, doc_dict):
        """
        Step three of the pillowtop processor:
        Finish transport of doc if needed. Your subclass should implement this
        """
        return None
