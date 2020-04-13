from couchforms.jsonobject_extensions import GeoPointProperty

__test__ = {
    'GeoPointProperty': GeoPointProperty,
}


def setUpModule():
    from corehq.elastic import get_es_new, debug_assert
    debug_assert(get_es_new())
