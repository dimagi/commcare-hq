from datetime import timedelta
from threading import Thread
import time
import uuid

from functools import wraps
from memoized import memoized
import itertools

from dimagi.utils.logging import notify_exception


class NestableTimer(object):
    """Timer object that can be nested. Used by ``TimingContext``.
    """
    def __init__(self, name, is_root=True):
        self.name = name
        self.beginning = None
        self.end = None
        self.subs = []
        self.root = self if is_root else None
        self.parent = None
        self.uuid = uuid.uuid4()

    def init(self, root, parent):
        self.root = root
        self.parent = parent

    def start(self):
        self.beginning = time.time()

    def stop(self):
        self.end = time.time()

    def append(self, timer):
        timer.init(self.root, self)
        self.subs.append(timer)

    @property
    def duration(self):
        """Get timer duration in seconds"""
        if self.beginning and self.end:
            return self.end - self.beginning
        elif self.beginning:
            return time.time() - self.beginning

    @property
    def percent_of_total(self):
        if self.duration and self.root and self.root.duration:
            return self.duration / self.root.duration * 100
        else:
            return None

    @property
    def percent_of_parent(self):
        if self.duration and self.parent and self.parent.duration:
            return self.duration / self.parent.duration * 100
        else:
            return None

    def to_dict(self):
        timer_dict = {
            'name': self.name,
            'duration': self.duration,
            'percent_total': self.percent_of_total,
            'percent_parent': self.percent_of_parent,
            'subs': [sub.to_dict() for sub in self.subs]
        }
        if not self.duration:
            timer_dict.update({
                'beginning': self.beginning,
                'end': self.end
            })
        return timer_dict

    def to_list(self, exclude_root=False):
        root = [] if exclude_root else [self]
        return root + list(itertools.chain(*[sub.to_list() for sub in self.subs]))

    @property
    def is_leaf_node(self):
        return not self.subs

    @property
    def is_root_node(self):
        return not self.parent

    @property
    @memoized
    def full_name(self):
        if self.is_root_node:
            return self.name
        return "%s.%s" % (self.parent.full_name, self.name)

    def __repr__(self):
        return "NestableTimer(name='{}', beginning={}, end={}, parent='{}', subs='{}')".format(
            self.name,
            self.beginning,
            self.end,
            self.parent.name if self.parent else '',
            self.subs
        )


class TimingContext(object):
    """Context manager for timing operations. Particularly useful for doing nested timing.

    Example usage:
        def sleep():
            time.sleep(0.1)

        def inner_sleep(timing_context):
            sleep()
            with timing_context('inner_sleep'):
                sleep()

        with TimingContext('demo_timing') as context:
            sleep()
            with context('level0'):
                inner_sleep(context)
    """
    def __init__(self, name=None):
        self.root = NestableTimer(name, is_root=True)
        self.stack = [self.root]

    def __call__(self, name):
        timer = NestableTimer(name)
        current = self.peek()
        current.append(timer)
        self.stack.append(timer)
        return self

    def peek(self):
        return self.stack[-1]

    def is_finished(self):
        return not self.stack

    def is_started(self):
        """Check if the timer has been started

        Returns false if the timer has not yet started or was started
        and then stopped, otherwise true.
        """
        return bool(self.stack) and self.peek().beginning is not None

    def start(self):
        if self.is_started():
            raise TimerError("timer already started")
        self.peek().start()

    def stop(self, name=None):
        if name is None:
            name = self.root.name
        timer = self.peek()
        if timer.name != name:
            notify_exception(
                None,
                "stopping wrong timer: {} (expected {})".format(timer.name, name),
                details={"self": self, "timer": timer},
            )
            return
        if timer.beginning is None:
            raise TimerError("timer not started")
        assert timer.end is None, "timer already ended"
        self.stack.pop().stop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop(self.peek().name)

    def to_dict(self):
        """Get timing data as a recursive dictionary of the format:
        {
            "name": "demo_timing",
            "duration": 0.3,
            "percent_total": 100.0,
            "percent_parent": null,
            "subs": [
                {
                    "name": "level0",
                    "duration": 0.2,
                    "percent_total": 66.66,
                    "percent_parent": 66.66,
                    "subs": [...]
                }
            ]
        }
        """
        return self.root.to_dict()

    @property
    def duration(self):
        return self.root.duration

    def to_list(self, exclude_root=False):
        """Get the list of ``NestableTimer`` objects in hierarchy order"""
        return self.root.to_list(exclude_root)

    def __repr__(self):
        return "TimingContext(root='{}')".format(
            self.root
        )


class TimerError(Exception):
    pass


def time_method():
    """Decorator to get timing information on a class method

    The class must have a TimingContext instance as self.timing_context
    """
    def decorator(fn):
        @wraps(fn)
        def _inner(self, *args, **kwargs):
            if self.timing_context.is_started():
                tag = f"{type(self).__name__}.{fn.__name__}"
                with self.timing_context(tag):
                    return fn(self, *args, **kwargs)
            else:
                return fn(self, *args, **kwargs)
        return _inner
    return decorator


DURATION_REPORTING_THRESHOLD = "_duration_reporting_threshold"


def set_request_duration_reporting_threshold(seconds):
    """Decorator to override the default reporting threshold for a view.

    If requests to the view take longer than the threshold a Sentry event
    will get created.

    :param seconds: Requests that take longer than this many seconds to process
        will be reported to Sentry. See ``corehq.middleware.LogLongRequestMiddleware``
        for where the duration check takes place.
    """
    def decorator(view):
        setattr(view, DURATION_REPORTING_THRESHOLD, seconds)
        return view

    return decorator


class ManagementCommandTimer(Thread):

    def __init__(self, interval=1):
        Thread.__init__(self)
        self.interval = interval

    def __enter__(self):
        print('Beginning execution...')
        self.is_running = True
        self.count = 1
        self.start_time = time.time()
        self.start()

    def run(self):
        while self.is_running:
            time.sleep(1)
            if self.count * self.interval * 60 < self.duration:
                self.count += 1
                print(f'Execution duration: {timedelta(seconds=self.duration)}...')

    def stop(self):
        self.is_running = False

    @property
    def duration(self):
        return time.time() - self.start_time

    def __exit__(self, exc_type, exc_value, tb):
        print(f"Completed in {timedelta(seconds=self.duration)}.")
        self.is_running = False
        return not exc_value


def time_command(interval=1):
    """Prints out every {interval} minutes a command has been running, i.e.
        Execution duration: 0:01:00.063119...
        Execution duration: 0:02:00.124327...
    """
    def decorator(fn):
        def _inner(self, *args, **kwargs):
            with ManagementCommandTimer(interval):
                return fn(self, *args, **kwargs)
        return _inner
    return decorator
