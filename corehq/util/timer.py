import time

import itertools


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
        if self.beginning and self.end:
            return self.end - self.beginning

    @property
    def percent_of_total(self):
        return (self.duration / self.root.duration * 100) if self.duration and self.root else None

    @property
    def percent_of_parent(self):
        return (self.duration / self.parent.duration * 100) if self.parent else None

    def to_dict(self):
        return {
            'name': self.name,
            'duration': self.duration,
            'percent_total': self.percent_of_total,
            'percent_parent': self.percent_of_parent,
            'subs': [sub.to_dict() for sub in self.subs]
        }

    def to_list(self):
        timers = [self] + list(itertools.chain(*[sub.to_list() for sub in self.subs]))
        return timers

    def __repr__(self):
        return "NestableTimer(name='{}', beginning={}, end={}, parent='{}')".format(
            self.name,
            self.beginning,
            self.end,
            self.parent.name if self.parent else ''
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
        return self.stack[len(self.stack) - 1]

    def __enter__(self):
        self.peek().start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        timer = self.stack.pop()
        timer.stop()

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
        return self.to_dict()['duration']

    def to_list(self):
        """Get the list of ``NestableTimer`` objects in hierarchy order"""
        return self.root.to_list()
