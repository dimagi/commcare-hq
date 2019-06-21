from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import random
from functools import wraps
import cProfile
import resource
import os
import gc
import logging

from datetime import datetime
from django.conf import settings
from corehq.util.decorators import ContextDecorator
from corehq.util.python_compatibility import soft_assert_type_text
from dimagi.utils.modules import to_function
import six

logger = logging.getLogger(__name__)

try:
    PROFILE_LOG_BASE = settings.PROFILE_LOG_BASE
except Exception:
    PROFILE_LOG_BASE = "/tmp"

# Source: http://code.djangoproject.com/wiki/ProfilingDjango


def profile(log_file):
    return profile_prod(log_file, 1, None)


def profile_prod(log_file, probability, limit):
    """Profile some callable.

    This decorator uses the hotshot profiler to profile some callable (like
    a view function or method) and dumps the profile data somewhere sensible
    for later processing and examination.

    :param log_file: If it's a relative path, it places it under the PROFILE_LOG_BASE.
        It also inserts a time stamp into the file name, such that
        'my_view.prof' become 'my_view-2018-06-07T12:46:56.367347.prof', where the time stamp is in UTC.
        This makes it easy to run and compare multiple trials.
    :param probability: A number N between 0 and 1 such that P(profile) ~= N
    :param limit: The maximum number of profiles to record.
    """
    assert isinstance(probability, (int, float)), 'probability must be numeric'
    assert 0 <= probability <= 1, 'probability must be in range [0, 1]'
    assert not limit or isinstance(limit, int), 'limit must be an integer'

    if not os.path.isabs(log_file):
        log_file = os.path.join(PROFILE_LOG_BASE, log_file)

    def _outer(f):
        if probability <= 0:
            return f

        base, ext = os.path.splitext(log_file)

        header = '=' * 100
        logger.warn("""
        %(header)s
        Profiling enabled for %(module)s.%(name)s with probability %(prob)s and limit %(limit)s.
        Output will be written to %(base)s-[datetime]%(ext)s
        %(header)s
        """, {
            'header': header, 'module': f.__module__, 'name': f.__name__,
            'prob': probability, 'base': base, 'ext': ext, 'limit': limit
        })

        class Scope:
            """Class to keep outer scoped variable"""
            profile_count = 0

        @wraps(f)
        def _inner(*args, **kwargs):
            hit_limit = limit and Scope.profile_count > limit
            if hit_limit or random.random() > probability:
                return f(*args, **kwargs)
            else:
                Scope.profile_count += 1
                # Add a timestamp to the profile output when the callable
                # is actually called.
                final_log_file = '{}-{}{}'.format(base, datetime.now().isoformat(), ext)

                prof = cProfile.Profile()
                try:
                    ret = prof.runcall(f, *args, **kwargs)
                finally:
                    prof.dump_stats(final_log_file)
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
            @wraps(func)
            def profiled_func(*args, **kwargs):
                try:
                    profiler = LineProfiler()
                    profiler.add_function(func)
                    for f in follow:
                        if isinstance(f, six.string_types):
                            soft_assert_type_text(f)
                            f = to_function(f)
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


class resident_set_size(ContextDecorator):
    """Shows how much memory was allocated to the python process (the resident set
    size) before and after the function this wraps. Can also be used as a context manager.

    Can be used to debug memory leaks.

    `man getrusage` for more information
    """
    def __init__(self, enter_debugger=False):
        self.initial_size = 0
        self.enter_debugger = enter_debugger

    def __enter__(self):
        self.initial_size = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print('Resident Set Size before: {}kb'.format(self.initial_size))

    def __exit__(self, exc_type, exc_val, exc_tb):
        gc.collect()
        final_size = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print('Resident Set Size after: {}kb'.format(final_size))
        print('Resident Set Size total: {}kb'.format(final_size - self.initial_size))
        if self.enter_debugger:
            try:
                import ipdb
                # NOTE: hit 'u' when debugger starts to enter the previous frame
                ipdb.set_trace()
            except ImportError:
                import pdb
                # NOTE: hit 'u' when debugger starts to enter the previous frame
                pdb.set_trace()
