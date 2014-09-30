import logging
from corehq.apps.receiverwrapper.util import get_version_from_appversion_text

try:
    from .test_repeater import *
    from .test_submissions import *
    from .test_submit_errors import *
    from .test_auth import *
    from .test_app_id import *
    from .test_guess_phone_type import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    logging.exception(e)
    raise(e)

__test__ = {
    'get_version_from_appversion_text': get_version_from_appversion_text,
}
