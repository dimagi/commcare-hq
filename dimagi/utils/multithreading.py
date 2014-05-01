from __future__ import absolute_import
import logging
from time import sleep
from threading import Thread
try:
    # Python 2.x
    import Queue as queue
except ImportError:
    # Python 3
    import queue

class ErrorObject(object):
    def __init__(self, *args, **kwargs):
        self.error_occurred = False

def worker_thread(q, err, function, *args, **kwargs):
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            break
        except Exception as e:
            # No need to do any locking here
            err.error_occurred = True
            logging.exception("Error in worker_thread")
            break

        try:
            function(item, *args, **kwargs)
        except Exception as e:
            err.error_occurred = True
            logging.exception("Error in %s" % function.__name__)

def process_fast(items, function, num_threads=4, item_goal=None, max_threads=50,
    args=None, kwargs=None):
    """
    Spawns a number of threads which will process the given items.
    items - the list of items to process
    function - the function to call on each item; should accept the item as the
      first argument, and any other args or kwargs sent here
    num_threads - number of threads to use if item_goal is None
    item_goal - if specified, the number of threads will be chosen so that each
      thread should process about this many items
    max_threads - used as a limit to the number of threads if item_goal is
      specified

    This function does not return until all items are processed.
    Raises RuntimeError if at least one thread raised an exception. Thread
      exceptions are logged using logging.exception.
    """
    if item_goal:
        num_threads = (len(items) / item_goal) + 1
        num_threads = min(num_threads, max_threads)

    q = queue.Queue()
    for item in items:
        q.put(item)

    err = ErrorObject()
    passed_args = (q, err, function) + (args or ())
    kwargs = kwargs or {}
    threads = []
    for i in range(num_threads):
        t = Thread(target=worker_thread, args=passed_args, kwargs=kwargs)
        t.start()
        threads.append(t)

    # Wait until the queue is empty. Don't use q.join() because that could keep
    # this thread lingering if something goes wrong and the queue's tasks aren't
    # marked as done.
    threads_alive = 50
    while threads_alive > 0:
        sleep(1)
        count = 0
        for thread in threads:
            if thread.is_alive():
                count += 1
        threads_alive = count

    if err.error_occurred:
        raise RuntimeError("Error occurred calling process_fast. Check "
            "couchlog for details.")

