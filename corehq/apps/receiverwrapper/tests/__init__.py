from corehq.apps.receiverwrapper.util import (
    get_commcare_version_from_appversion_text,
    get_version_from_appversion_text,
)

__test__ = {
    'get_version_from_appversion_text': get_version_from_appversion_text,
    'get_commcare_version_from_appversion_text': get_commcare_version_from_appversion_text,
}


def setUpModule():
    from corehq.elastic import get_es_new, debug_assert
    debug_assert(get_es_new())
