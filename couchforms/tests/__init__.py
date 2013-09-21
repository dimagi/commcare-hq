import logging
try:
    from .test_archive import *
    from .test_meta import *
    from .test_duplicates import *
    from .test_edits import *
    from .test_namespaces import *
    from .test_auth import *
    from .test_post import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    logging.error(e)
    raise(e)
