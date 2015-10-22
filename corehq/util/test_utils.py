from __future__ import absolute_import
import json
import mock
import os

from fakecouch import FakeCouchDb
from functools import wraps
from django.conf import settings


class UnitTestingRequired(Exception):
    pass


def unit_testing_only(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if not settings.UNIT_TESTING:
            raise UnitTestingRequired(
                'You may only call {} during unit testing'.format(fn.__name__))
        return fn(*args, **kwargs)
    return inner
unit_testing_only.__test__ = False


class TestFileMixin(object):

    file_path = ''
    root = ''

    @property
    def base(self):
        return self.get_base()

    @classmethod
    def get_base(cls, override_path=None):
        path = override_path or cls.file_path
        return os.path.join(cls.root, *path)

    @classmethod
    def get_path(cls, name, ext, override_path=None):
        return os.path.join(cls.get_base(override_path), '%s.%s' % (name, ext))

    @classmethod
    def get_file(cls, name, ext, override_path=None):
        with open(cls.get_path(name, ext, override_path)) as f:
            return f.read()

    @classmethod
    def write_xml(cls, name, xml, override_path=None):
        with open(cls.get_path(name, 'xml', override_path), 'w') as f:
            return f.write(xml)

    @classmethod
    def get_json(cls, name, override_path=None):
        return json.loads(cls.get_file(name, 'json', override_path))

    @classmethod
    def get_xml(cls, name, override_path=None):
        return cls.get_file(name, 'xml', override_path)


def flag_enabled(toggle_class):
    """
    Decorate test methods with this to mock the lookup

        @flag_enabled(toggles.MULTIPLE_LOCATIONS_PER_USER)
        def test_something_fancy(self):
            something.which_depends(on.MULTIPLE_LOCATIONS_PER_USER)
    """
    return mock.patch(
        '.'.join([toggle_class.__module__, toggle_class.__class__.__name__, 'enabled']),
        new=lambda *args: True,
    )


class DocTestMixin(object):
    """To be mixed in with a TestCase"""

    def assert_docs_equal(self, doc1, doc2):
        self.assertEqual(type(doc1), type(doc2))
        self.assertEqual(doc1.to_json(), doc2.to_json())

    def assert_doc_lists_equal(self, docs1, docs2):
        self.assertEqual(
            sorted([(doc._id, doc.to_json()) for doc in docs1]),
            sorted([(doc._id, doc.to_json()) for doc in docs2]),
        )


def mock_out_couch(views=None, docs=None):
    """
    Mock out calls to couch so you can use SimpleTestCase

        @mock_out_couch()
        class TestMyStuff(SimpleTestCase):
            ...

    You can optionally pass default return values for specific views and doc
    gets.  See the FakeCouchDb docstring for more specifics.
    """

    class FakeCouchDb_(FakeCouchDb):
        def __init__(self):
            super(FakeCouchDb_, self).__init__(views=views, docs=docs)

    return mock.patch('dimagi.ext.couchdbkit.Document.get_db', new=FakeCouchDb_)
