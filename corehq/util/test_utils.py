import functools
import json
import logging
import os
import traceback
import uuid
from collections import namedtuple
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta
from functools import wraps
from io import StringIO, open
from textwrap import indent, wrap
from time import time
from unittest import SkipTest, TestCase

from django.conf import settings
from django.db import connections
from django.db.backends import utils
from django.test.utils import CaptureQueriesContext

import mock

from corehq.util.context_managers import drop_connected_signals
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


class trap_extra_setup(ContextDecorator):
    """Conditionally skip test on error

    Use this decorator/context manager to skip tests that would
    otherwise fail in environments where some or all external
    dependencies have not been configured. It raises
    `unittest.case.SkipTest` if one of the given exceptions is raised
    and `settings.SKIP_TESTS_REQUIRING_EXTRA_SETUP` is true (see
    dev_settings.py). Hard failures should be preserved in environments
    where external dependencies are expected to be setup (travis), so
    `settings.SKIP_TESTS_REQUIRING_EXTRA_SETUP` should be false there.
    """

    def __init__(self, *exceptions, **kw):
        assert exceptions, "at least one argument is required"
        assert all(issubclass(e, Exception) for e in exceptions), exceptions
        self.exceptions = exceptions
        self.msg = kw.pop("msg", "")
        assert not kw, "unknown keyword args: {}".format(kw)
        self.skip = getattr(settings, "SKIP_TESTS_REQUIRING_EXTRA_SETUP", False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, err, tb):
        if isinstance(err, self.exceptions) and self.skip:
            msg = self.msg
            if msg:
                msg += ": "
            raise SkipTest("{}{}: {}".format(msg, type(err).__name__, err))


def softer_assert(comment=None):
    """A shortcut function to get the patch for disabling hardened soft_assert for tests"""
    return mock.patch("corehq.util.soft_assert.core.is_hard_mode", new=lambda: False)


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
        ext = '.%s' % ext if ext and not ext.startswith('.') else ext
        return os.path.join(cls.get_base(override_path), '%s%s' % (name, ext))

    @classmethod
    def get_file(cls, name, ext, override_path=None):
        with open(cls.get_path(name, ext, override_path), encoding='utf-8') as f:
            return f.read()

    @classmethod
    def write_xml(cls, name, xml, override_path=None):
        with open(cls.get_path(name, '.xml', override_path), 'w', encoding='utf-8') as f:
            return f.write(xml)

    @classmethod
    def get_json(cls, name, override_path=None):
        return json.loads(cls.get_file(name, '.json', override_path))

    @classmethod
    def get_xml(cls, name, override_path=None):
        return cls.get_file(name, '.xml', override_path).encode('utf-8')


class flag_enabled(object):
    """
    Decorate test methods with this to mock the lookup

        @flag_enabled('SELF_DESTRUCT_ON_SUBMIT')
        def test_something_fancy(self):
            something.which_depends(on.SELF_DESTRUCT_ON_SUBMIT)
    """
    enabled = True

    def __init__(self, toggle_name, is_preview=False):
        location = 'corehq.feature_previews' if is_preview else 'corehq.toggles'
        self.patches = [
            mock.patch('.'.join([location, toggle_name, method_name]),
                       new=lambda *args, **kwargs: self.enabled)
            for method_name in ['enabled', 'enabled_for_request']
        ]

    def __call__(self, fn):
        for patch in self.patches:
            fn = patch(fn)
        return fn

    def __enter__(self):
        for patch in self.patches:
            patch.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        for patch in self.patches:
            patch.stop()


class flag_disabled(flag_enabled):
    enabled = False


class DocTestMixin(object):
    """To be mixed in with a TestCase"""

    def assert_docs_equal(self, doc1, doc2):
        self.assertEqual(type(doc1), type(doc2))
        self.assertEqual(doc1.to_json(), doc2.to_json())

    def assert_doc_sets_equal(self, docs1, docs2):
        self.assertEqual(
            sorted([(doc._id, type(doc), doc.to_json()) for doc in docs1]),
            sorted([(doc._id, type(doc), doc.to_json()) for doc in docs2]),
        )

    def assert_doc_lists_equal(self, docs1, docs2):
        self.assertEqual(
            [(type(doc), doc.to_json()) for doc in docs1],
            [(type(doc), doc.to_json()) for doc in docs2],
        )


class mock_out_couch(object):
    """
    Mock out calls to couch so you can use SimpleTestCase

        @mock_out_couch()
        class TestMyStuff(SimpleTestCase):
            ...

        with mock_out_couch() as fake_db:
            fake_db.save_doc({...})

    You can optionally pass default return values for specific views and doc
    gets.  See the FakeCouchDb docstring for more specifics.
    """
    def __init__(self, views=None, docs=None):
        from fakecouch import FakeCouchDb
        self.views = views
        self.docs = docs
        self.db = FakeCouchDb(views=views, docs=docs)

        @classmethod
        def _get_db(*args):
            return self.db

        self.patches = [
            mock.patch('dimagi.ext.couchdbkit.Document.get_db', new=_get_db),
            mock.patch('dimagi.ext.couchdbkit.SafeSaveDocument.get_db', new=_get_db),
            mock.patch('dimagi.utils.couch.undo.UndoableDocument.get_db', new=_get_db),
        ]

    def __call__(self, func):
        if isinstance(func, type):
            return self._patch_class(func)
        else:
            @wraps(func)
            def decorated(*args, **kwds):
                with self:
                    return func(*args, **kwds)
            return decorated

    def _patch_class(self, klass):
        for patch in self.patches:
            klass = patch(klass)
        return klass

    def __enter__(self):
        for patch in self.patches:
            patch.start()

        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        for patch in self.patches:
            patch.stop()


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
                print(self.fn, 'failed with the following settings:')
                for key, value in run_config.settings.items():
                    print('settings.{} = {!r}'.format(key, value))
                raise


def call_with_settings(fn, settings_dict, args, kwargs):
    original_settings = {key: getattr(settings, key, None) for key in settings_dict}
    try:
        # set settings to new values
        for key, value in settings_dict.items():
            setattr(settings, key, value)
        fn(*args, **kwargs)
    finally:
        # set settings back to original values
        for key, value in original_settings.items():
            setattr(settings, key, value)


def run_with_multiple_configs(fn, run_configs, nose_tags=None):
    from nose.plugins.attrib import attr
    helper = RunWithMultipleConfigs(fn, run_configs)

    @functools.wraps(fn)
    @attr(**(nose_tags or {}))
    def inner(*args, **kwargs):
        return helper(*args, **kwargs)

    return inner


class capture_log_output(ContextDecorator):
    """
    Can be used as either a context manager or decorator.
    """

    def __init__(self, logger_name, level=logging.DEBUG):
        self.logger = logging.getLogger(logger_name)
        self.new_level = level
        self.original_level = self.logger.level
        self.original_handlers = self.logger.handlers
        for handler in self.original_handlers:
            self.logger.removeHandler(handler)
        self.output = StringIO()
        self.logger.addHandler(logging.StreamHandler(self.output))

    def __enter__(self):
        self.logger.setLevel(self.new_level)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)
        for handler in self.logger.handlers:
            self.logger.removeHandler(handler)
        for handler in self.original_handlers:
            self.logger.addHandler(handler)

    def get_output(self):
        return self.output.getvalue()


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


def timelimit(limit):
    """Create a decorator that asserts a run time limit

    An assertion error is raised if the decorated function returns
    without raising an error and the elapsed run time is longer than
    the allowed time limit.

    This decorator can be used to extend the time limit imposed by
    --max-test-time when `corehq.tests.noseplugins.timing.TimingPlugin`
    is enabled.

    Usage:

        @timelimit
        def lt_one_second():
            ...

        @timelimit(0.5)
        def lt_half_second():
            ...

    See also: `patch_max_test_time` for overriding time limits for an
    entire test group (module, test class, etc.)

    :param limit: number of seconds or a callable to decorate. If
    callable, the time limit defaults to one second.
    """
    if callable(limit):
        return timelimit((limit, timedelta(seconds=1)))
    if not isinstance(limit, tuple):
        limit = timedelta(seconds=limit)
        return lambda func: timelimit((func, limit))
    func, limit = limit
    @wraps(func)
    def time_limit(*args, **kw):
        from corehq.tests.noseplugins.timing import add_time_limit
        add_time_limit(limit.total_seconds())
        start = datetime.utcnow()
        rval = func(*args, **kw)
        elapsed = datetime.utcnow() - start
        assert elapsed < limit, f"{func.__name__} took too long: {elapsed}"
        return rval
    return time_limit


def patch_max_test_time(limit):
    """Temporarily override test time limit (--max-test-time)

    Note: this is only useful when spanning multiple test events because
    the limit must be present at the _end_ of a test event to take
    effect. Therefore it will do nothing if used within the context of a
    single test (use `timelimit` for that). It also does not affect the
    time limit on the final teardown fixture (in which the patch is
    removed).

    :param limit: New time limit (seconds).

    Usage at module level:

        TIME_LIMIT = patch_max_test_time(9)

        def setup_module():
            TIME_LIMIT.start()

        def teardown_module():
            TIME_LIMIT.stop()

    Usage as class decorator:

        @patch_max_test_time(9)
        class TestSomething(TestCase):
            ...
    """
    from corehq.tests.noseplugins.timing import patch_max_test_time
    return patch_max_test_time(limit)


patch_max_test_time.__test__ = False


def get_form_ready_to_save(metadata, is_db_test=False):
    from corehq.form_processor.parsers.form import process_xform_xml
    from corehq.form_processor.utils import get_simple_form_xml, convert_xform_to_json
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    from corehq.form_processor.models import Attachment

    assert metadata is not None
    metadata.domain = metadata.domain or uuid.uuid4().hex
    form_id = uuid.uuid4().hex
    form_xml = get_simple_form_xml(form_id=form_id, metadata=metadata)

    if is_db_test:
        wrapped_form = process_xform_xml(metadata.domain, form_xml).submitted_form
    else:
        interface = FormProcessorInterface(domain=metadata.domain)
        form_json = convert_xform_to_json(form_xml)
        wrapped_form = interface.new_xform(form_json)
        wrapped_form.domain = metadata.domain
        interface.store_attachments(wrapped_form, [
            Attachment(name='form.xml', raw_content=form_xml, content_type='text/xml')
        ])
    wrapped_form.received_on = metadata.received_on
    wrapped_form.app_id = metadata.app_id
    return wrapped_form


def make_es_ready_form(metadata, is_db_test=False):
    # this is rather complicated due to form processor abstractions and ES restrictions
    # on what data needs to be in the index and is allowed in the index
    wrapped_form = get_form_ready_to_save(metadata, is_db_test=is_db_test)
    json_form = wrapped_form.to_json()
    json_form['form']['meta'].pop('appVersion')  # hack - ES chokes on this
    return WrappedJsonFormPair(wrapped_form, json_form)


def create_and_save_a_form(domain):
    """
    Very basic way to save a form, not caring at all about its contents
    """
    from corehq.form_processor.utils import TestFormMetadata
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    metadata = TestFormMetadata(domain=domain)
    form = get_form_ready_to_save(metadata)
    FormProcessorInterface(domain=domain).save_processed_models([form])
    return form


def _create_case(domain, **kwargs):
    from casexml.apps.case.mock import CaseBlock
    from corehq.apps.hqcase.utils import submit_case_blocks
    return submit_case_blocks(
        [CaseBlock.deprecated_init(**kwargs).as_text()], domain=domain
    )


def create_and_save_a_case(domain, case_id, case_name, case_properties=None, case_type=None,
        drop_signals=True, owner_id=None, user_id=None):
    from casexml.apps.case.signals import case_post_save
    from corehq.form_processor.signals import sql_case_post_save

    kwargs = {
        'create': True,
        'case_id': case_id,
        'case_name': case_name,
        'update': case_properties,
    }

    if case_type:
        kwargs['case_type'] = case_type

    if owner_id:
        kwargs['owner_id'] = owner_id

    if user_id:
        kwargs['user_id'] = user_id

    if drop_signals:
        # this avoids having to deal with all the reminders code bootstrap
        with drop_connected_signals(case_post_save), drop_connected_signals(sql_case_post_save):
            form, cases = _create_case(domain, **kwargs)
    else:
        form, cases = _create_case(domain, **kwargs)

    return cases[0]


@contextmanager
def create_test_case(domain, case_type, case_name, case_properties=None, drop_signals=True,
        case_id=None, owner_id=None, user_id=None):
    from corehq.apps.sms.tasks import delete_phone_numbers_for_owners
    from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
    from corehq.form_processor.utils.general import should_use_sql_backend
    from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import delete_schedule_instances_by_case_id

    case = create_and_save_a_case(domain, case_id or uuid.uuid4().hex, case_name,
        case_properties=case_properties, case_type=case_type, drop_signals=drop_signals,
        owner_id=owner_id, user_id=user_id)
    try:
        yield case
    finally:
        delete_phone_numbers_for_owners([case.case_id])
        delete_schedule_instances_by_case_id(domain, case.case_id)
        if should_use_sql_backend(domain):
            CaseAccessorSQL.hard_delete_cases(domain, [case.case_id])
        else:
            case.delete()


create_test_case.__test__ = False


def teardown(do_teardown):
    """A decorator that adds teardown logic to a test function/method

    NOTE this will not work for nose test generator functions.
    """
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kw):
            try:
                res = func(*args, **kw)
                assert res is None, "{} returned value {!r}".format(func, res)
            finally:
                do_teardown(*args, **kw)
        return wrapper
    return decorate


def set_parent_case(domain, child_case, parent_case, relationship='child', identifier='parent'):
    """
    Creates a parent-child relationship between child_case and parent_case.
    """
    from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex

    parent = CaseStructure(case_id=parent_case.case_id)
    CaseFactory(domain).create_or_update_case(
        CaseStructure(
            case_id=child_case.case_id,
            indices=[CaseIndex(
                related_structure=parent,
                identifier=identifier,
                relationship=relationship
            )],
        )
    )


def update_case(domain, case_id, case_properties, user_id=None):
    from casexml.apps.case.mock import CaseBlock
    from casexml.apps.case.util import post_case_blocks

    kwargs = {
        'case_id': case_id,
        'update': case_properties,
    }

    if user_id:
        kwargs['user_id'] = user_id

    post_case_blocks(
        [CaseBlock.deprecated_init(**kwargs).as_xml()], domain=domain
    )


def make_make_path(current_directory):
    """
    returns a utility function for generating absolute paths
    from paths relative to `current_directory`

    example:

        _make_path = make_make_path(__file__)
        _make_path('files', 'myfile.txt')
    """

    def _make_path(*args):
        return os.path.join(os.path.dirname(current_directory), *args)

    return _make_path


class PatchMeta(type):
    """A metaclass to patch all inherited classes.

    Usage:
    class BaseTest(TestCase, metaclass=PatchMeta):
        patch = mock.patch('something.do.patch', .....)
    """

    patch = None

    def __init__(self, *args, **kwargs):
        super(PatchMeta, self).__init__(*args, **kwargs)
        self.patch(self)


class CursorDebugWrapperWithTraceback(utils.CursorDebugWrapper):
    def execute(self, sql, params=None):
        start = time()
        try:
            return utils.CursorWrapper.execute(self, sql, params)
        finally:
            stop = time()
            duration = stop - start
            sql = self.db.ops.last_executed_query(self.cursor, sql, params)
            self.db.queries_log.append({
                'start': start,
                'sql': sql,
                'time': "%.3f" % duration,
                'traceback': traceback.format_stack()
            })

    def executemany(self, sql, param_list):
        start = time()
        try:
            return utils.CursorWrapper.executemany(self, sql, param_list)
        finally:
            stop = time()
            duration = stop - start
            try:
                times = len(param_list)
            except TypeError:           # param_list could be an iterator
                times = '?'
            self.db.queries_log.append({
                'start': start,
                'sql': '%s times: %s' % (times, sql),
                'time': "%.3f" % duration,
                'traceback': traceback.format_stack()
            })


class capture_sql(ContextDecorator):
    """
    Capture SQL executed on ALL databases listed in settings
    ```
    with capture_sql() as capture:
        # do some quries

    capture.print_sql(with_traceback=False)
    ```
    """
    def __init__(self):
        self.query_contexts = {}
        self.wrapper = utils.CursorDebugWrapper

    def __enter__(self):
        utils.CursorDebugWrapper = CursorDebugWrapperWithTraceback
        self._stack = ExitStack()
        for db in settings.DATABASES:
            context = CaptureQueriesContext(connections[db])
            self.query_contexts[db] = context
            self._stack.enter_context(context)
        return self

    def __exit__(self, *exc_details):
        utils.CursorDebugWrapper = self.wrapper
        self._stack.__exit__(*exc_details)

    @property
    def queries_by_db(self):
        return {
            db: context.captured_queries
            for db, context in self.query_contexts.items()
        }

    def print_sql(self, with_traceback=False, width=150):
        for db, queries in self.queries_by_db.items():
            if not queries:
                continue
            print(f'\n------- Queries for Database "{db}" ({len(queries)}) ---------')
            for q in queries:
                out = f"{q['sql']} (took {q['time']})"
                print('\n{}'.format(indent('\n'.join(wrap(out, width)), '\t')))
                if with_traceback:
                    print('\n{}'.format(indent(''.join(q['traceback']), '\t\t')))

    def print_sql_chronologically(self, with_traceback=False, width=150):
        all_queries = sorted([
            (db, query)
            for db, queries in self.queries_by_db.items()
            for query in queries
        ], key=lambda q: q[1]['start'])
        for db, query in all_queries:
            out = f"({db}) {query['sql']} (took {query['time']})"
            print('\n{}'.format(indent('\n'.join(wrap(out, width)), '\t')))
            if with_traceback:
                print('\n{}'.format(indent(''.join(query['traceback']), '\t\t')))


def require_db_context(fn):
    """
    Only run 'fn' in DB tests
    :param fn: a setUpModule or tearDownModule function
    """
    @wraps(fn)
    def inner(*args, **kwargs):
        from corehq.apps.domain.models import Domain
        if not isinstance(Domain.get_db(), mock.Mock):
            return fn(*args, **kwargs)
    return inner
