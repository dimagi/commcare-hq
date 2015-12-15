from collections import defaultdict
import logging
import datetime
from dimagi.utils.parsing import json_format_date
from .exceptions import EmitterTypeError


class CalculatorMeta(type):
    _counter = 0

    def __new__(mcs, name, bases, attrs):
        emitters = set()
        filters = set()
        parents = [p for p in bases if isinstance(p, CalculatorMeta)]
        for attr in attrs:
            if getattr(attrs[attr], '_fluff_emitter', None):
                emitters.add(attr)
            if getattr(attrs[attr], '_fluff_filter', False):
                filters.add(attr)

        # needs to inherit emitters and filters from all parents
        for parent in parents:
            emitters.update(parent._fluff_emitters)
            filters.update(parent._fluff_filters)

        cls = super(CalculatorMeta, mcs).__new__(mcs, name, bases, attrs)
        cls._fluff_emitters = emitters
        cls._fluff_filters = filters
        cls._counter = mcs._counter
        mcs._counter += 1
        return cls


class Calculator(object):
    __metaclass__ = CalculatorMeta

    window = None

    # set by IndicatorDocumentMeta
    fluff = None
    slug = None

    # set by CalculatorMeta
    _fluff_emitters = None
    _fluff_filters = None

    def __init__(self, window=None, filter=None):
        if window is not None:
            self.window = window
        if not isinstance(self.window, (type(None), datetime.timedelta)):
            if any(getattr(self, e)._fluff_emitter == 'date' for e in self._fluff_emitters):
                # If window is set to something other than a timedelta
                # fail here and not whenever that's run into below
                raise NotImplementedError(
                    'window must be timedelta, not %s' % type(self.window))
        self._filter = filter

    def filter(self, item):
        return self._filter is None or self._filter.filter(item)

    def passes_filter(self, item):
        """
        This is pretty confusing, but there are two mechanisms for having a filter,
        one via the explicit filter function and the other being the @filter_by decorator
        that can be applied to other functions.
        """
        return self.filter(item) and all(
            (getattr(self, slug)(item) for slug in self._fluff_filters)
        )

    def to_python(self, value):
        return value

    def calculate(self, item):
        passes_filter = self.passes_filter(item)
        values = {}
        for slug in self._fluff_emitters:
            fn = getattr(self, slug)
            try:
                values[slug] = (
                    list(fn(item))
                    if passes_filter else []
                )
                for val in values[slug]:
                    if val['group_by'] and len(val['group_by']) != len(self.fluff.group_by):
                        raise Exception("group_by returned by emitter is of different length to default group_by")
            except Exception:
                logging.exception((
                    "Error in emitter %s > %s > %s: '%s'"
                ) % (
                    self.fluff.__name__,
                    self.slug,
                    slug,
                    item.get_id,
                ))
                raise
        return values

    def get_result(self, key, date_range=None, reduce=True, verbose_results=False):
        """
        If your Calculator does not have a window set, you must pass a tuple of
        date or datetime objects to date_range
        """
        if verbose_results:
            assert not reduce, "can't have reduce set for verbose results"

        if date_range is not None:
            start, end = date_range
        elif self.window:
            now = self.fluff.get_now()
            start = now - self.window
            end = now
        result = {}
        for emitter_name in self._fluff_emitters:
            shared_key = [self.fluff._doc_type] + key + [self.slug, emitter_name]
            emitter = getattr(self, emitter_name)
            emitter_type = emitter._fluff_emitter
            q_args = {
                'reduce': reduce,
            }
            if emitter_type == 'date':
                assert isinstance(date_range, tuple) or self.window, (
                    "You must either set a window on your Calculator "
                    "or pass in a date range")
                if start > end:
                    q_args['descending'] = True
                q = self.fluff.view(
                    'fluff/generic',
                    startkey=shared_key + [json_format_date(start)],
                    endkey=shared_key + [json_format_date(end)],
                    **q_args
                ).all()
            elif emitter_type == 'null':
                q = self.fluff.view(
                    'fluff/generic',
                    key=shared_key + [None],
                    **q_args
                ).all()
            else:
                raise EmitterTypeError(
                    'emitter type %s not recognized' % emitter_type
                )

            if reduce:
                try:
                    result[emitter_name] = q[0]['value'][emitter._reduce_type]
                except IndexError:
                    result[emitter_name] = 0
            else:
                # clean ids
                def strip(id_string):
                    prefix = '%s-' % self.fluff.__name__
                    assert id_string.startswith(prefix)
                    return id_string[len(prefix):]
                for row in q:
                    row['id'] = strip(row['id'])

                if not verbose_results:
                    # strip down to ids
                    result[emitter_name] = [row['id'] for row in q]
                else:
                    result[emitter_name] = q

        return result

    def aggregate_results(self, keys, reduce=True, verbose_results=False, date_range=None):

        def iter_results():
            for key in keys:
                result = self.get_result(key, reduce=reduce, date_range=date_range,
                                         verbose_results=verbose_results)
                for slug, value in result.items():
                    yield slug, value

        if reduce:
            results = defaultdict(int)
            for slug, value in iter_results():
                results[slug] += value
        elif not verbose_results:
            results = defaultdict(set)
            for slug, value in iter_results():
                results[slug].update(value)
        else:
            results = defaultdict(list)
            for slug, value in iter_results():
                results[slug].extend(value)

        return results
