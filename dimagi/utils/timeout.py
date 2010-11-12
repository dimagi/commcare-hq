import threading

class TimeoutException(Exception):
    pass

class TimeoutTask(threading.Thread):
    def __init__(self, func, args, kwargs, cachefunc=None):
        threading.Thread.__init__(self)
        self.eval = lambda: func(*args, **kwargs)
        self.cachefunc = cachefunc

        self.expired = False
        self.result = None
        self.err = None

        self.lock = threading.Lock()

    def run(self):
        try:
            self.result = self.eval()
        except Exception, e:
            self.err = e

        with self.lock:
            if self.expired and self.cachefunc:
                self.cachefunc(self.result, self.err)

    def execute(self, timeout=None):
        self.start()
        self.join(timeout)
        with self.lock:
            if self.isAlive():
                self.expired = True
                raise TimeoutException()
            elif self.err:
                raise self.err
            else:
                return self.result

def timeout(n, cachefunc=None):
    """
    decorator to allow execution of a function for only a certain amount of time. if
    the specified time elapses and the function still has not returned, throw a
    TimeoutException. any exception in the function will propogate upward if it occurs
    before the timeout

    n: timeout in seconds
    cachefunc(result, exception): if the function times out, when it does finally finish,
    the result will be passed to this function for offline handling
    """
    def timeout_n(f):
        return lambda *args, **kwargs: TimeoutTask(f, args, kwargs, cachefunc).execute(n)
    return timeout_n

"""
example:

@timeout(10, notify_ready)
def really_long_computation(key):
    try:
        return get_from_cache(key)
    except NotInCache:
        answer = compute_meaning_of_life(key)
        store_in_cache(key, answer)
        return answer

def notify_ready(value, err):
    if err:
        print 'oops; error occurred [%s]' % err
    else:
        print 'value is ready now [%s]' % value

try:
    print really_long_computation(key)
except TimeoutException:
    print 'taking too long; try again later'
"""
