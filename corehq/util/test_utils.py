from __future__ import absolute_import
import uuid
import functools
import json
import logging
import mock
import os
from unittest import TestCase
from collections import namedtuple
from contextlib import contextmanager

from unittest.case import SkipTest

from fakecouch import FakeCouchDb
from functools import wraps
from django.conf import settings
import sys
from corehq.util.decorators import ContextDecorator


WrappedJsonFormPair = namedtuple('WrappedJsonFormPair', ['wrapped_form', 'json_form'])


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


@contextmanager
def trap_extra_setup(*exceptions):
    """Conditioinally skip test on error

    Use this context manager to skip tests that would otherwise fail in
    environments where some or all external dependencies have not been
    configured. It raises `unittest.case.SkipTest` if one of the given
    exceptions is raised and `settings.SKIP_TESTS_REQUIRING_EXTRA_SETUP`
    is true (see dev_settings.py). Hard failures should be preserved in
    environments where external dependencies are expected to be setup
    (travis), so `settings.SKIP_TESTS_REQUIRING_EXTRA_SETUP` should be
    false there.
    """
    assert exceptions, "at least one argument is required"
    skip = getattr(settings, "SKIP_TESTS_REQUIRING_EXTRA_SETUP", False)
    try:
        yield
    except exceptions as err:
        if skip:
            raise SkipTest("{}: {}".format(type(err).__name__, err))
        raise


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


def flag_enabled(toggle_class_string):
    """
    Decorate test methods with this to mock the lookup

        @flag_enabled('MULTIPLE_LOCATIONS_PER_USER')
        def test_something_fancy(self):
            something.which_depends(on.MULTIPLE_LOCATIONS_PER_USER)
    """
    return mock.patch(
        '.'.join(['corehq.toggles', toggle_class_string, 'enabled']),
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
    db = FakeCouchDb(views=views, docs=docs)
    def _get_db(*args):
        return db

    return mock.patch('dimagi.ext.couchdbkit.Document.get_db', new=_get_db)


def NOOP(*args, **kwargs):
    pass


class RunConfig(object):

    def __init__(self, settings, pre_run=None, post_run=None):
        self.settings = settings
        self.pre_run = pre_run or NOOP
        self.post_run = post_run or NOOP


class RunWithMultipleConfigs(object):
    def __init__(self, fn, run_configs):
        self.fn = fn
        self.run_configs = run_configs

    def __call__(self, *args, **kwargs):
        for run_config in self.run_configs:

            def fn_with_pre_and_post(*args, **kwargs):
                # make sure the pre and post run also run with the right settings
                run_config.pre_run(*args, **kwargs)
                self.fn(*args, **kwargs)
                run_config.post_run(*args, **kwargs)

            try:
                call_with_settings(fn_with_pre_and_post, run_config.settings, args, kwargs)
            except Exception:
                print self.fn, 'failed with the following settings:'
                for key, value in run_config.settings.items():
                    print 'settings.{} = {!r}'.format(key, value)
                raise


def call_with_settings(fn, settings_dict, args, kwargs):
    keys = settings_dict.keys()
    original_settings = {key: getattr(settings, key, None) for key in keys}
    try:
        # set settings to new values
        for key, value in settings_dict.items():
            setattr(settings, key, value)
        fn(*args, **kwargs)
    finally:
        # set settings back to original values
        for key, value in original_settings.items():
            setattr(settings, key, value)


def run_with_multiple_configs(fn, run_configs):
    helper = RunWithMultipleConfigs(fn, run_configs)

    @functools.wraps(fn)
    def inner(*args, **kwargs):
        return helper(*args, **kwargs)

    return inner


class log_sql_output(ContextDecorator):
    """
    Can be used as either a context manager or decorator.
    """
    def __init__(self):
        self.logger = logging.getLogger('django.db.backends')
        self.new_level = logging.DEBUG
        self.original_level = self.logger.level
        self.original_debug_value = settings.DEBUG
        self.original_handlers = self.logger.handlers
        for handler in self.original_handlers:
            self.logger.removeHandler(handler)
        self.logger.addHandler(logging.StreamHandler(sys.stdout))

    def __enter__(self):
        settings.DEBUG = True
        self.logger.setLevel(self.new_level)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)
        settings.DEBUG = self.original_debug_value
        for handler in self.logger.handlers:
            self.logger.removeHandler(handler)
        for handler in self.original_handlers:
            self.logger.addHandler(handler)


def generate_cases(argsets, cls=None):
    """Make a decorator to generate a set of parameterized test cases

    Until we have nose generator tests...

    Usage:

        @generate_cases([
            ("foo", "bar"),
            ("bar", "foo"),
        ], TestThing)
        def test_foo(self, foo, bar)
            self.assertEqual(self.thing[foo], bar)

    Note: generated test cases cannot be run individually by name since
    their parameterized names are not valid function names. This was a
    tradeoff with making parameterized tests identifiable on failure.

    :param argsets: A sequence of argument tuples or dicts, one for each
    test case to be generated.
    :param cls: Optional test case class to which tests should be added.
    """
    def add_cases(test_func):
        if cls is None:
            class Test(TestCase):
                pass
            Test.__name__ = test_func.__name__
        else:
            Test = cls

        for args in argsets:
            def test(self, args=args):
                if isinstance(args, dict):
                    return test_func(self, **args)
                return test_func(self, *args)

            test.__name__ = test_func.__name__ + repr(args)
            assert not hasattr(Test, test.__name__), \
                "duplicate test case: {} {}".format(Test, test.__name__)

            setattr(Test, test.__name__, test)

        if cls is None:
            # Only return newly created test class; otherwise the test
            # runner will run tests on cls twice. Explanation: the
            # returned value will be bound to the name of the decorated
            # test_func; if cls is provided then there will be two names
            # bound to the same test class
            return Test

    return add_cases


def get_form_ready_to_save(metadata):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    from corehq.form_processor.utils import get_simple_form_xml
    from corehq.form_processor.utils import convert_xform_to_json

    assert metadata is not None
    metadata.domain = metadata.domain or uuid.uuid4().hex
    form_id = uuid.uuid4().hex
    form_xml = get_simple_form_xml(form_id=form_id, metadata=metadata)
    form_json = convert_xform_to_json(form_xml)
    wrapped_form = FormProcessorInterface(domain=metadata.domain).new_xform(form_json)
    wrapped_form.domain = metadata.domain
    wrapped_form.received_on = metadata.received_on
    return wrapped_form


def make_es_ready_form(metadata):
    # this is rather complicated due to form processor abstractions and ES restrictions
    # on what data needs to be in the index and is allowed in the index
    wrapped_form = get_form_ready_to_save(metadata)
    json_form = wrapped_form.to_json()
    json_form['form']['meta'].pop('appVersion')  # hack - ES chokes on this
    return WrappedJsonFormPair(wrapped_form, json_form)
