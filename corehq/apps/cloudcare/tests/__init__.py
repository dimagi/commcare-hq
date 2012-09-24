try:
    from .test_mobile_worker_interface import *
    from .test_admin_interface import *
except ImportError, e:
    import logging
    logging.exception(e)
    raise
