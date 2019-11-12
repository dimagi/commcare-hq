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
from dimagi.utils.modules import to_function

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
