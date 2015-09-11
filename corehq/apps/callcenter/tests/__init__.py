try:
    from corehq.apps.callcenter.tests.test_indicators import *
    from corehq.apps.callcenter.tests.test_indicator_fixture import *
    from corehq.apps.callcenter.tests.test_utils import *
    from corehq.apps.callcenter.tests.test_models import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    import logging
    logging.exception(e)
    raise

from corehq.apps.callcenter.utils import DomainLite
__test__ = {
    'DomainLite.midnights': DomainLite.midnights
}
