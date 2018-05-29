# All code in this file is temporary while comparing results of adjacency
# list and MPTT queries. LocationQueriesMixin.accessible_to_user must also be
# adjusted when it is removed (and see other uses of ComparedQuerySet).
from __future__ import absolute_import
from __future__ import unicode_literals

import time
from collections import Counter, defaultdict
from contextlib import contextmanager

from django.conf import settings
from django.db.models.query import QuerySet

from corehq.util.datadog.gauges import datadog_counter
from corehq.util.datadog.utils import bucket_value
from corehq.util.soft_assert import soft_assert


class ComparedQuerySet(object):
    """Compare results and times of MPTT and CTE queries"""

    def __init__(self, mptt_set, cte_set, timing_context):
        self._mptt_set = None
        self._cte_set = cte_set
        assert self._cte_set is not None
        if isinstance(timing_context, ComparedQuerySet):
            timing_context = timing_context._timing.clone()
        self._timing = timing_context

    def __str__(self):
        return "MPTT query: {}\n\nCTE query: {}".format(
            self._mptt_set.query if self._mptt_set is not None else None,
            self._cte_set.query if self._cte_set is not None else None,
        )

    def __iter__(self):
        items1 = []
        finished = False
        with _commit_timing(self):
            if self._mptt_set is None:
                with self._timing("cte") as timer1:
                    for item in self._cte_set:
                        with timer1.pause():
                            yield item
                return
            try:
                with self._timing("mptt") as timer1:
                    for item in self._mptt_set:
                        items1.append(item)
                        with timer1.pause():
                            yield item
                finished = True
            finally:
                if self._cte_set is None:
                    return
                with self._timing("cte"):
                    items2 = list(self._cte_set)
                ids1 = [_identify(it) for it in items1]
                ids2 = [_identify(it) for it in items2]
                # Verify both sets contain the same items, ignoring sort order
                # Note: it's possible that there are duplicate elements.
                if (finished and Counter(ids1) != Counter(ids2)) or (
                        not finished and set(ids1) - set(ids2)):
                    _report_diff(self, ids1, ids2, "" if finished else "incomplete iteration")

    def __len__(self):
        with _commit_timing(self):
            if self._mptt_set is not None:
                with self._timing("mptt"):
                    len1 = len(self._mptt_set)
            if self._cte_set is not None:
                with self._timing("cte"):
                    len2 = len(self._cte_set)
        if self._mptt_set is None:
            return len2
        if self._cte_set is not None and len1 != len2:
            ids1 = [_identify(it) for it in self._mptt_set]
            ids2 = [_identify(it) for it in self._cte_set]
            _report_diff(self, ids1, ids2, "%s != %s" % (len1, len2))
        return len1

    def __getitem__(self, key):
        with _commit_timing(self):
            if self._mptt_set is not None:
                with self._timing("mptt"):
                    mptt_result = self._mptt_set.__getitem__(key)
            if self._cte_set is not None:
                with self._timing("cte"):
                    cte_result = self._cte_set.__getitem__(key)
        if isinstance(cte_result if self._mptt_set is None else mptt_result, QuerySet):
            if self._mptt_set is None:
                mptt_result = None
            elif self._cte_set is None:
                cte_result = None
            elif not isinstance(cte_result, QuerySet):
                _report_diff(self, mptt_result, cte_result)
            return ComparedQuerySet(mptt_result, cte_result, self)
        if self._mptt_set is None:
            return cte_result
        if self._cte_set is not None:
            if isinstance(mptt_result, list) and isinstance(cte_result, list):
                ids1 = [_identify(it) for it in mptt_result]
                ids2 = [_identify(it) for it in cte_result]
            else:
                ids1 = _identify(mptt_result)
                ids2 = _identify(cte_result)
            if ids1 != ids2:
                _report_diff(self, ids1, ids2)
        return mptt_result

    def exists(self, *args, **kw):
        with _commit_timing(self):
            if self._mptt_set is not None:
                with self._timing("mptt"):
                    ex1 = self._mptt_set.exists(*args, **kw)
            if self._cte_set is not None:
                with self._timing("cte"):
                    ex2 = self._cte_set.exists(*args, **kw)
        if self._mptt_set is None:
            return ex2
        if self._cte_set is not None and ex1 != ex2:
            _report_diff(self, ex1, ex2)
        return ex1

    def union(self, *other_qs, **kwargs):
        other_mptt = [qs._mptt_set if isinstance(qs, ComparedQuerySet) else qs
            for qs in other_qs]
        other_cte = [qs._cte_set if isinstance(qs, ComparedQuerySet) else qs
            for qs in other_qs]
        return ComparedQuerySet(
            self._mptt_set.union(*other_mptt, **kwargs) if self._mptt_set is not None else None,
            self._cte_set.union(*other_cte, **kwargs) if self._cte_set is not None else None,
            self,
        )

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
            self._mptt_set.filter(id__in=ids_query._mptt_set) if self._mptt_set is not None else None,
            self._cte_set.filter(id__in=ids_query._cte_set) if self._cte_set is not None else None,
            TimingContext("accessible_to_user"),
        )
        result._timing += ids_query._timing
        return result


def _identify(item):
    return getattr(item, "id", item)


def _make_get_method(name):
    def method(self, *args, **kw):
        with _commit_timing(self):
            if self._mptt_set is not None:
                with self._timing("mptt"):
                    obj1 = getattr(self._mptt_set, name)(*args, **kw)
            if self._cte_set is not None:
                with self._timing("cte"):
                    obj2 = getattr(self._cte_set, name)(*args, **kw)
        if self._mptt_set is None:
            return obj2
        if self._cte_set is not None and _identify(obj1) != _identify(obj2):
            _report_diff(self, obj1, obj2)
        return obj1
    method.__name__ = str(name)  # unicode_literals: must be bytes on PY2
    return method


def _make_qs_method(name):
    def method(self, *args, **kw):
        return ComparedQuerySet(
            getattr(self._mptt_set, name)(*args, **kw) if self._mptt_set is not None else None,
            getattr(self._cte_set, name)(*args, **kw) if self._cte_set is not None else None,
            self,
        )
    method.__name__ = str(name)  # unicode_literals: must be bytes on PY2
    return method


for _make_method, name in [
    # methods that get a model instance
    (_make_get_method, "count"),
    (_make_get_method, "get"),
    (_make_get_method, "first"),
    (_make_get_method, "last"),
    # methods that return a new QuerySet
    (_make_qs_method, "annotate"),
    (_make_qs_method, "defer"),
    (_make_qs_method, "distinct"),
    (_make_qs_method, "exclude"),
    (_make_qs_method, "filter"),
    (_make_qs_method, "none"),
    (_make_qs_method, "only"),
    (_make_qs_method, "order_by"),
    (_make_qs_method, "prefetch_related"),
    (_make_qs_method, "select_related"),
    (_make_qs_method, "values"),
    (_make_qs_method, "values_list"),
    # from subclasses of QuerySet
    (_make_qs_method, "location_ids"),
]:
    setattr(ComparedQuerySet, name, _make_method(name))


def _report_diff(cqs, obj1, obj2, context=""):
    message = """ComparedQuerySet difference:
    MPTT query: {cqs._mptt_set.query}

    CTE query: {cqs._cte_set.query}

    MPTT result: {obj1!r}
    CTE result:  {obj2!r}
    {context}""".format(**locals())

    soft_assert(to='{}@{}'.format('dmiller', 'dimagi.com'))(False, message)


@contextmanager
def _commit_timing(queryset):
    # only send to datadog on initial query evaluation
    result_set = queryset._mptt_set if queryset._mptt_set is not None else queryset._cte_set
    commit = result_set._result_cache is None
    try:
        yield
    finally:
        if commit and result_set._result_cache is not None:
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
