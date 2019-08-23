
from django.conf import settings
from six.moves import range

if not settings.configured:
    settings.configure(DEBUG=True)


from mock import MagicMock, NonCallableMock, patch
from unittest2 import TestCase

from memoized import memoized
from dimagi.utils.chunked import chunked
from dimagi.utils.read_only import ReadOnlyObject
from dimagi.utils.couch.sync_docs import sync_design_docs, copy_designs


class DimagiUtilsTestCase(TestCase):

    def test_memoized_function(self):
        @memoized
        def f(n=0):
            return n**2

        self.assertEquals(f(), 0)
        self.assertEquals(f.get_cache(), {(0,): 0})
        self.assertEquals(f(0), 0)
        self.assertEquals(f.get_cache(), {(0,): 0})
        self.assertEquals(f(2), 4)
        self.assertEquals(sorted(f.get_cache().items()), [((0,), 0), ((2,), 4)])

    def test_memoized_class(self):
        calls = {'get_full_name': 0, 'full_name': 0, 'complicated_method': 0}

        @memoized
        class Person(object):
            get_full_name_calls = 0
            full_name_calls = 0
            complicated_method_calls = 0

            def __init__(self, first_name, last_name):
                self.first_name = first_name
                self.last_name = last_name

            @property
            @memoized
            def full_name(self):
                calls['full_name'] = calls['full_name'] + 1
                return "%s %s" % (self.first_name, self.last_name)

            @memoized
            def get_full_name(self):
                calls['get_full_name'] = calls['get_full_name'] + 1
                return "%s %s" % (self.first_name, self.last_name)

            def __repr__(self):
                return "%s(%r, %r)" % (self.__class__.__name__, self.first_name, self.last_name)

            @memoized
            def complicated_method(self, a, b=10, *args, **kwargs):
                calls['complicated_method'] = calls['complicated_method'] + 1
                return a, b, args, kwargs

        p = Person("Danny", "Roberts")
        self.assertEquals(p.get_full_name(), 'Danny Roberts')
        self.assertEquals(calls['get_full_name'], 1)
        self.assertEquals(p.get_full_name(), 'Danny Roberts')
        self.assertEquals(calls['get_full_name'], 1)

        self.assertEquals(p.full_name, 'Danny Roberts')
        self.assertEquals(calls['full_name'], 1)
        self.assertEquals(p.full_name, 'Danny Roberts')
        self.assertEquals(calls['full_name'], 1)

        self.assertEquals(Person("Danny", "Roberts")._full_name_cache, {(): 'Danny Roberts'})
        self.assertEquals(Person.get_full_name.get_cache(p), {(): 'Danny Roberts'})

        self.assertEquals(p.complicated_method(5), (5, 10, (), {}))
        self.assertEquals(calls['complicated_method'], 1)
        self.assertEquals(p.complicated_method(5), (5, 10, (), {}))
        self.assertEquals(calls['complicated_method'], 1)

        self.assertEquals(p.complicated_method(1, 2, 3, 4, 5, foo='bar'), (1, 2, (3, 4, 5), {'foo': 'bar'}))
        self.assertEquals(calls['complicated_method'], 2)

        q = Person("Joe", "Schmoe")
        self.assertEquals(q.get_full_name(), 'Joe Schmoe')
        self.assertEquals(calls['get_full_name'], 2)

    def test_chunked(self):
        self.assertEquals(list(chunked(list(range(10)), 4)), [
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (8, 9)
        ])

    def test_ReadOnlyObject(self):

        from couchdbkit import Document, StringListProperty
        log = []

        def read_log():
            x = log[:]
            del log[:]
            return x

        class Thing(Document):
            words = StringListProperty()
            @property
            def calc(self):
                for i, word in enumerate(self.words):
                    log.append(i)
                    yield word + '!'
        thing = Thing(words=['danny', 'is', 'so', 'clever'])
        thing = ReadOnlyObject(thing)
        self.assertEquals(thing.words, ['danny', 'is', 'so', 'clever'])
        self.assertEquals(thing.words, ['danny', 'is', 'so', 'clever'])
        self.assertIs(thing.words, thing.words)
        self.assertEquals(thing.calc, ['danny!', 'is!', 'so!', 'clever!'])
        self.assertEquals(read_log(), [0, 1, 2, 3])
        self.assertEquals(thing.calc, ['danny!', 'is!', 'so!', 'clever!'])
        self.assertEquals(read_log(), [])
        self.assertIs(thing.calc, thing.calc)

    def test_sync_design_docs(self):
        db = NonCallableMock()

        with patch('dimagi.utils.couch.sync_docs.push', MagicMock()) as mock_push:
            sync_design_docs(db, 'design_dir', 'design_name')
            mock_push.assert_called_with('design_dir', db, docid='_design/design_name', force=True)

    def test_sync_design_docs_tmp(self):
        db = MagicMock()

        with patch('dimagi.utils.couch.sync_docs.push', MagicMock()) as mock_push:
            sync_design_docs(db, 'design_dir', 'design_name', temp='tmp')
            mock_push.assert_called_with('design_dir', db, docid='_design/design_name-tmp', force=True)
            self.assertEquals(len(db.mock_calls), 4)

    def test_copy_designs(self):
        db = MagicMock()
        copy_designs(db, 'design_name')

        db.copy_doc.assert_called_once_with('_design/design_name-tmp', '_design/design_name')
        db.__delitem__.assert_called_with('_design/design_name-tmp')
