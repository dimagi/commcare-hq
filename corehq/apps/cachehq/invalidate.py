from corehq.pillows import cacheinvalidate
from dimagi.utils.decorators.memoized import memoized


@memoized
def get_cache_pillow():
    return cacheinvalidate.CacheInvalidatePillow()


def invalidate_document(document, deleted=False):
    """
    Invalidates a document in the cached_core caching framework.
    """
    # this is a hack that use the caching pillow invalidation that was intended to be
    # rolled out to track this globally.
    get_cache_pillow().change_trigger({
        'doc': document.to_json(),
        'id': document._id,
        'deleted': deleted,
    })
