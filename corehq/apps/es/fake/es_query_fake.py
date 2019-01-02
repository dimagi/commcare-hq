from __future__ import absolute_import
from __future__ import unicode_literals
from copy import deepcopy
import datetime
import logging
import pytz
import uuid
from corehq.apps.es.es_query import ESQuerySet
from corehq.apps.es.utils import values_list
from six.moves import filter
from corehq.elastic import ScanResult

FILTER_TEMPLATE = """
    def {fn}(self, ...):
        # called with args {args!r} and kwargs {kwargs!r}
        return self._filtered(lambda doc: ...)
"""


def check_deep_copy(method):
    """
    When constructing a query the real ES query deep copies all filters.
    This decorator should be used on any method that adds a new filter
    """
    def _check_deep_copy(*args, **kwargs):
        for arg in args:
            deepcopy(args)
        for key, value in kwargs.items():
            deepcopy(value)
        return method(*args, **kwargs)
    return _check_deep_copy


class ESQueryFake(object):

    _start = 0
    _size = None
    _sort_field = None
    _sort_desc = False
    # just to make ESQuerySet happy
    _exclude_source = None
    _legacy_fields = None
    _source_fields = None

    def __init__(self, result_docs=None):
        if result_docs is None:
            result_docs = list(self._all_docs)

        self._result_docs = result_docs

    def _clone(self, result_docs=None):
        if result_docs is None:
            result_docs = list(self._result_docs)

        clone = self.__class__(result_docs=result_docs)
        clone._start = self._start
        clone._size = self._size
        clone._sort_field = self._sort_field
        clone._sort_desc = self._sort_desc
        clone._exclude_source = self._exclude_source
        clone._legacy_fields = self._legacy_fields
        clone._source_fields = self._source_fields
        return clone

    def _filtered(self, filter_function):
        return self._clone(result_docs=list(filter(filter_function, self._result_docs)))

    @classmethod
    def save_doc(cls, doc):
        if '_id' not in doc:
            doc['_id'] = 'silly-fake-id-{}'.format(uuid.uuid4().hex[:8])
        doc = cls.transform_doc(doc)
        cls._get_all_docs().append(doc)

    @staticmethod
    def transform_doc(doc):
        return doc

    @classmethod
    def reset_docs(cls):
        del cls._get_all_docs()[:]

    @classmethod
    def remove_doc(cls, doc_id):
        cls._all_docs = [doc for doc in cls._all_docs if doc['_id'] != doc_id]

    @classmethod
    def _get_all_docs(cls):
        cls_name = cls.__name__
        try:
            return cls._all_docs
        except AttributeError:
            raise AttributeError('{} must define attribute _all_docs'.format(cls_name))

    def values_list(self, *fields, **kwargs):
        if kwargs.pop('scroll', False):
            hits = self.scroll()
        else:
            hits = self.run().hits

        return values_list(hits, *fields, **kwargs)

    @check_deep_copy
    def search_string_query(self, search_string, default_fields=None):
        if not search_string:
            return self
        if default_fields:
            return self._filtered(
                lambda doc: any(doc[field] is not None and (search_string in doc[field])
                                for field in default_fields))
        else:
            raise NotImplementedError("We'll cross that bridge when we get there")

    @check_deep_copy
    def start(self, start):
        clone = self._clone()
        clone._start = start
        return clone

    @check_deep_copy
    def size(self, size):
        clone = self._clone()
        clone._size = size
        return clone

    @check_deep_copy
    def sort(self, field, desc=False):
        clone = self._clone()
        clone._sort_field = field
        clone._sort_desc = desc
        return clone

    def get_ids(self):
        return [h['_id'] for h in self.run().hits]

    def source(self, fields):
        self._source_fields = fields
        return self

    def run(self):
        result_docs = list(self._result_docs)
        total = len(result_docs)
        if self._sort_field:
            result_docs.sort(key=lambda doc: doc[self._sort_field],
                             reverse=self._sort_desc)
        if self._size is not None:
            result_docs = result_docs[self._start:self._start + self._size]
        else:
            result_docs = result_docs[self._start:]

        def _get_doc(doc):
            if self._source_fields:
                return {key: doc[key] for key in self._source_fields if key in doc}
            return doc

        return ESQuerySet({
            'hits': {
                'hits': [{'_source': _get_doc(doc)} for doc in result_docs],
                'total': total,
            },
        }, self)

    def scroll(self):
        result_docs = list(self._result_docs)
        total = len(result_docs)
        if self._sort_field:
            result_docs.sort(key=lambda doc: doc[self._sort_field],
                             reverse=self._sort_desc)
        if self._size is not None:
            result_docs = result_docs[self._start:self._start + self._size]
        else:
            result_docs = result_docs[self._start:]

        def _get_doc(doc):
            if self._source_fields:
                return {key: doc[key] for key in self._source_fields if key in doc}
            return doc

        es_query_set = (ESQuerySet.normalize_result(self,
                                                    {'_source': _get_doc(r)}) for r in result_docs)
        return ScanResult(total, es_query_set)

    @check_deep_copy
    def term(self, field, value):
        if isinstance(value, (list, tuple, set)):
            valid_terms = set(value)
        else:
            valid_terms = set([value])

        def _term_query(doc):
            if isinstance(doc[field], list):
                return set(doc[field]).intersection(valid_terms)
            return doc[field] in valid_terms

        return self._filtered(_term_query)

    @check_deep_copy
    def date_range(self, field, gt=None, gte=None, lt=None, lte=None):
        def format_time(t):
            if t:
                t = datetime.datetime(*(t.timetuple()[:6]))
                return pytz.UTC.localize(t)
            return t

        gt = format_time(gt)
        gte = format_time(gte)
        lt = format_time(lt)
        lte = format_time(lte)

        def _date_comparison(doc):
            if gt and doc:
                if not doc[field] > gt:
                    return False
            if gte and doc:
                if not doc[field] >= gte:
                    return False
            if lt and doc:
                if not doc[field] < lt:
                    return False
            if lte and doc:
                if not doc[field] <= lte:
                    return False

            return True

        return self._filtered(_date_comparison)

    def __getattr__(self, item):
        """
        To make it really easy to add methods to a fake only as needed by real tests,
        this prints out any calls to methods that aren't defined, with a suggested
        template to use for the function, but without raising an error.
        That way when you run a test, you'll get a print out for all of the methods
        you need to overwrite all at once.

        """
        cls_name = self.__class__.__name__

        if item == '_all_docs':
            raise AttributeError('{} must define attribute _all_docs'.format(cls_name))
        elif item.startswith('_'):
            raise AttributeError("'{}' object has no attribute '{}'"
                                 .format(cls_name, item))
        else:
            def f(*args, **kwargs):
                logging.error(
                    ("You need to define {cls}.{fn}. Here's a start" + FILTER_TEMPLATE)
                    .format(cls=cls_name, fn=item, args=args, kwargs=kwargs)
                )
                return self
            return f


class HQESQueryFake(ESQueryFake):

    def doc_id(self, doc_id):
        try:
            doc_ids = list(doc_id)
        except TypeError:
            doc_ids = [doc_id]
        return self._filtered(lambda doc: doc['_id'] in doc_ids)

    def domain(self, domain):
        return self._filtered(lambda doc: doc['domain'] == domain)
