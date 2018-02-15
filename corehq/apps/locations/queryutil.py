# All code in this file is temporary while comparing results of adjacency
# list and MPTT queries. LocationQueriesMixin.accessible_to_user must also be
# adjusted when it is removed (and see other uses of ComparedQuerySet).
from __future__ import absolute_import
from __future__ import unicode_literals

import time
from collections import defaultdict
from contextlib import contextmanager

from corehq.util.datadog.gauges import datadog_counter
from corehq.util.datadog.utils import bucket_value


class ComparedQuerySet(object):
    """Measure times of MPTT queries

    Will be used to compare results and times of MPTT and CTE queries,
    hence the name and slightly verbose implementation.
    """

    def __init__(self, mptt_set, timing_context):
        self._mptt_set = mptt_set
        if isinstance(timing_context, ComparedQuerySet):
            timing_context = timing_context._timing.clone()
        self._timing = timing_context

    def __iter__(self):
        with _commit_timing(self):
            with self._timing("mptt") as timer1:
                for item in self._mptt_set:
                    with timer1.pause():
                        yield item

    def __len__(self):
        with _commit_timing(self):
            with self._timing("mptt"):
                return len(self._mptt_set)

    def get(self, *args, **kw):
        with _commit_timing(self):
            with self._timing("mptt"):
                return self._mptt_set.get(*args, **kw)

    def exists(self, *args, **kw):
        with _commit_timing(self):
            with self._timing("mptt"):
                return self._mptt_set.exists(*args, **kw)

    def accessible_to_user(self, domain, user):
        # mostly copied from models.py:LocationQueriesMixin

        if user.has_permission(domain, 'access_all_locations'):
            return self.filter(domain=domain)

        assigned_location_ids = user.get_location_ids(domain)
        if not assigned_location_ids:
            return self.none()  # No locations are assigned to this user

        from .models import SQLLocation
        ids_query = SQLLocation.objects.get_locations_and_children(assigned_location_ids)
        assert isinstance(ids_query, ComparedQuerySet), ids_query
        result = ComparedQuerySet(
            self._mptt_set.filter(id__in=ids_query._mptt_set),
            TimingContext("accessible_to_user"),
        )
        result._timing += ids_query._timing
        return result


def _make_method(name):
    def method(self, *args, **kw):
        return ComparedQuerySet(
            getattr(self._mptt_set, name)(*args, **kw),
            self,
        )
    method.__name__ = str(name)  # unicode_literals: must be bytes on PY2
    return method


for name in [
    "annotate",
    "filter",
    "none",
    "order_by",
    "values",
    "values_list",
    # from subclasses of QuerySet
    "location_ids",
]:
    setattr(ComparedQuerySet, name, _make_method(name))


@contextmanager
def _commit_timing(queryset):
    # only send to datadog on initial query evaluation
    commit = queryset._mptt_set._result_cache is None
    try:
        yield
    finally:
        if commit and queryset._mptt_set._result_cache is not None:
            timing = queryset._timing
            for key in timing.timers:
                bucket = bucket_value(timing.duration(key), TIME_BUCKETS, "s")
                datadog_counter(
                    'commcare.locations.%s.%s.count' % (timing.name, key),
                    tags=['duration:%s' % bucket],
                )


TIME_BUCKETS = (.001, .01, .1, 1, 5, 10, 30, 60)


class TimingContext(object):

    def __init__(self, name):
        self.name = name
        self.timers = defaultdict(list)

    def __iadd__(self, other):
        for key, timers in other.timers.items():
            self.timers[key].extend(timers)
        return self

    def __call__(self, key):
        timer = Timer()
        self.timers[key].append(timer)
        return timer

    def clone(self):
        context = type(self)(self.name)
        context += self
        return context

    def duration(self, key):
        return sum(t.duration for t in self.timers.get(key, []))


class Timer(object):
    """Measure elapsed time from __init__ to __exit__

    Duration is measured in seconds, and is available after __exit__.
    """

    def __init__(self):
        self.start = time.time()
        self.pauses = []

    def __enter__(self):
        return self

    def __exit__(self, *ignored):
        self.duration = time.time() - self.start - sum(p.duration for p in self.pauses)

    def pause(self):
        timer = Timer()
        self.pauses.append(timer)
        return timer
