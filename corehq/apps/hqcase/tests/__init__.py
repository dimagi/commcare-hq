import logging
try:
    from .test_bugs import *
    from .test_case_assigment import *
    from .test_case_sharing import *
    from .test_explode_cases import *
    from .test_loadtest_users import *
    from .test_object_cache import *
    from .test_dbaccessors import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    logging.exception(str(e))
    raise
