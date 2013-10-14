from gevent.pool import Pool
from restkit.session import set_session; set_session("gevent")
from pillowtop import get_all_pillows


def start_pillows(pillows=None):
    """
    Actual runner for running pillow processes. Use this to run pillows.
    """
    start_pillows = pillows or get_all_pillows()
    pool = Pool(len(start_pillows))
    while True:
        for p in start_pillows:
            pool.spawn(p.run)
        pool.join()
        # Pillows if they ever finish will need to restart continue forever.

