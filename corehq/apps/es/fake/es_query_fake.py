import logging
import uuid
from corehq.apps.es.es_query import ESQuerySet
from corehq.apps.es.utils import values_list

FILTER_TEMPLATE = """
    def {fn}(self, ...):
        # called with args {args!r} and kwargs {kwargs!r}
        return self._filtered(lambda doc: ...)
"""


class ESQueryFake(object):

    _start = 0
    _size = None
    _sort_field = None
    _sort_desc = False
    # just to make ESQuerySet happy
    _fields = None

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
        clone._sort_field = self._sort_field
        clone._sort_desc = self._sort_desc
        clone._fields = self._fields
        return clone

    def _filtered(self, filter_function):
        return self._clone(result_docs=filter(filter_function, self._result_docs))

    @classmethod
    def save_doc(cls, doc):
        if '_id' not in doc:
            doc['_id'] = 'silly-fake-id-{}'.format(uuid.uuid4().hex[:8])
        cls._get_all_docs().append(doc)

    @classmethod
    def reset_docs(cls):
        del cls._get_all_docs()[:]

    @classmethod
    def _get_all_docs(cls):
        cls_name = cls.__name__
        try:
            return cls._all_docs
        except AttributeError:
            raise AttributeError('{} must define attribute _all_docs'.format(cls_name))

    def values_list(self, *fields, **kwargs):
        return values_list(self.run().hits, *fields, **kwargs)

    def search_string_query(self, search_string, default_fields=None):
        if default_fields:
            return self._filtered(
                lambda doc: any(doc[field] is not None and (search_string in doc[field])
                                for field in default_fields))
        else:
            raise NotImplementedError("We'll cross that bridge when we get there")

    def start(self, start):
        clone = self._clone()
        clone._start = start
        return clone

    def size(self, size):
        clone = self._clone()
        clone._size = size
        return clone

    def sort(self, field, desc=False):
        clone = self._clone()
        clone._sort_field = field
        clone._sort_desc = desc
        return clone

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

        return ESQuerySet({
            'hits': {
                'hits': [{'_source': doc} for doc in result_docs],
                'total': total,
            },
        }, self)

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
