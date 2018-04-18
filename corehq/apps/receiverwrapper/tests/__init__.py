from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.receiverwrapper.util import get_version_from_appversion_text, \
    get_commcare_version_from_appversion_text

__test__ = {
    'get_version_from_appversion_text': get_version_from_appversion_text,
    'get_commcare_version_from_appversion_text': get_commcare_version_from_appversion_text,
}
