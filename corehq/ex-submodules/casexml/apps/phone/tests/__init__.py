
def setUpModule():
    from corehq.elastic import get_es_new, debug_assert
    debug_assert(get_es_new())
