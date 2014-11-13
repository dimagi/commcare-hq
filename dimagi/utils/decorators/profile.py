import hotshot
import os
from datetime import datetime
from django.conf import settings

try:
    PROFILE_LOG_BASE = settings.PROFILE_LOG_BASE
except Exception:
    PROFILE_LOG_BASE = "/tmp"

# Source: http://code.djangoproject.com/wiki/ProfilingDjango

def profile(log_file):
    """Profile some callable.

    This decorator uses the hotshot profiler to profile some callable (like
    a view function or method) and dumps the profile data somewhere sensible
    for later processing and examination.

    It takes one argument, the profile log name. If it's a relative path, it
    places it under the PROFILE_LOG_BASE. It also inserts a time stamp into the 
    file name, such that 'my_view.prof' become 'my_view-20100211T170321.prof', 
    where the time stamp is in UTC. This makes it easy to run and compare 
    multiple trials.     
    """

    if not os.path.isabs(log_file):
        log_file = os.path.join(PROFILE_LOG_BASE, log_file)

    def _outer(f):
        def _inner(*args, **kwargs):
            # Add a timestamp to the profile output when the callable
            # is actually called.
            (base, ext) = os.path.splitext(log_file)
            base = base + "-" + datetime.now().strftime("%Y%m%dT%H%M%S%f")
            final_log_file = base + ext

            prof = hotshot.Profile(final_log_file)
            try:
                ret = prof.runcall(f, *args, **kwargs)
            finally:
                prof.close()
            return ret

        return _inner
    return _outer

try:
    from line_profiler import LineProfiler

    def line_profile(follow=[]):
        """
        Perform line profiling of a function.

        Will output the profile stats per line of each function included in the profiler.
        Output will be printed once per function call so take care not to use this on
        functions that get called many times.

        :param follow: list of additional functions that should be profiled

        Example output
        --------------

        File: demo.py
        Function: demo_follow at line 67
        Total time: 1.00391 s

        Line #      Hits         Time  Per Hit   % Time  Line Contents
        ==============================================================
            67                                           def demo_follow():
            68         1           34     34.0      0.0      r = random.randint(5, 10)
            69        11           81      7.4      0.0      for i in xrange(0, r):
            70        10      1003800 100380.0    100.0          time.sleep(0.1)

        File: demo.py
        Function: demo_profiler at line 72
        Total time: 1.80702 s

        Line #      Hits         Time  Per Hit   % Time  Line Contents
        ==============================================================
            72                                           @line_profile(follow=[demo_follow])
            73                                           def demo_profiler():
            74         1           17     17.0      0.0      r = random.randint(5, 10)
            75         9           66      7.3      0.0      for i in xrange(0, r):
            76         8       802921 100365.1     44.4          time.sleep(0.1)
            77
            78         1      1004013 1004013.0     55.6      demo_follow()
        """
        def inner(func):
            def profiled_func(*args, **kwargs):
                try:
                    profiler = LineProfiler()
                    profiler.add_function(func)
                    for f in follow:
                        profiler.add_function(f)
                    profiler.enable_by_count()
                    return func(*args, **kwargs)
                finally:
                    profiler.print_stats()
            return profiled_func
        return inner

except ImportError:
    def line_profile(follow=[]):
        "Helpful if you accidentally leave in production!"
        def inner(func):
            def nothing(*args, **kwargs):
                return func(*args, **kwargs)
            return nothing
        return inner
