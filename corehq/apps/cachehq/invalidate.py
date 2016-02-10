from corehq.pillows import cacheinvalidate
from dimagi.utils.decorators.memoized import memoized


@memoized
def get_cache_pillow(couch_db):
    return cacheinvalidate.CacheInvalidatePillow(couch_db=couch_db)


def invalidate_document(document, couch_db, deleted=False):
    """
    Invalidates a document in the cached_core caching framework.
    """
    # this is a hack that use the caching pillow invalidation that was intended to be
    # rolled out to track this globally.
    get_cache_pillow(couch_db).change_trigger({
        'doc': document.to_json(),
        'id': document._id,
        'deleted': deleted,
    })
