from corehq.pillows import cacheinvalidate

cache_pillow = cacheinvalidate.CacheInvalidatePillow()

def invalidate_document(document, deleted=False):
    """
    Invalidates a document in the cached_core caching framework.
    """
    # this is a hack that use the caching pillow invalidation that was intended to be
    # rolled out to track this globally.
    cache_pillow.change_trigger({
        'doc': document.to_json(),
        'id': document._id,
        'deleted': deleted,
    })
