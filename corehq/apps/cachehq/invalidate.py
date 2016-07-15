from corehq.pillows import cacheinvalidate
from corehq.pillows.cacheinvalidate import CacheInvalidateProcessor
from dimagi.utils.decorators.memoized import memoized


@memoized
def _get_cache_processor():
    return CacheInvalidateProcessor()


def invalidate_document(document, deleted=False):
    """
    Invalidates a document in the cached_core caching framework.
    """
    # this is a hack that use the caching pillow invalidation that was intended to be
    # rolled out to track this globally.
    _get_cache_processor().process_doc(document.to_json(), deleted)
