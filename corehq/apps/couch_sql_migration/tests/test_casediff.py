from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import defaultdict
from contextlib import contextmanager

import attr
import gevent
import six
from django.test import SimpleTestCase
from mock import patch

from .. import casediff as mod
from ..statedb import delete_state_db, init_state_db

log = logging.getLogger(__name__)


@patch.object(mod.CaseDiffQueue, "BATCH_SIZE", 2)
@patch.object(gevent.get_hub(), "SYSTEM_ERROR", BaseException)
class TestCaseDiffQueue(SimpleTestCase):

    def setUp(self):
        self.get_cases_patcher = patch(
            "corehq.form_processor.backends.couch.dbaccessors.CaseAccessorCouch.get_cases",
            self.get_cases,
        )
        self.get_cases_patcher.start()
        self.cases = {}
        self.diffed = defaultdict(int)

    def tearDown(self):
        self.get_cases_patcher.stop()
        delete_state_db("test")

    def test_case_diff(self):
        self.add_cases("c", "fx")
        with self.queue() as queue:
            queue.update({"c"}, "fx")
        self.assertDiffed("c")

    def test_diff_case_without_forms(self):
        self.add_cases("cx")
        with self.queue() as queue:
            queue.update({"cx"}, "fx")
        self.assertDiffed("cx")

    def test_diff_batching(self):
        self.add_cases("a b c d e", "fx")
        batch_size = mod.CaseDiffQueue.BATCH_SIZE
        assert batch_size < 3, batch_size
        with self.queue() as queue:
            queue.update({"a", "b", "c", "d", "e"}, "fx")
            self.assertLess(len(queue.pending_cases), batch_size)
            self.assertLess(len(queue.cases_to_diff), batch_size)
        self.assertDiffed("a b c d e")

    def test_get_cases_failure(self):
        self.add_cases("a b c", "f1")
        self.add_cases("d", "f2")
        # simulate a single call to couch failing
        with self.queue() as queue, self.get_cases_failure():
            queue.update({"a", "b", "c"}, "f1")
        with self.queue() as queue:
            queue.update({"d"}, "f2")
        self.assertDiffed("a b c d")

    def test_resume_after_couch_down(self):
        self.add_cases("a b c", "f1")
        self.add_cases("d", "f2")
        # simulate couch down all the way through queue __exit__
        with self.get_cases_failure(), self.queue() as queue:
            queue.update({"a", "b", "c"}, "f1")
        with self.queue() as queue:
            queue.update({"d"}, "f2")
        self.assertDiffed("a b c d")

    def test_diff_cases_failure(self):
        self.add_cases("a b c", "f1")
        self.add_cases("d", "f2")
        self.add_cases("e", "f3")
        with self.queue() as queue, self.diff_cases_failure():
            queue.update({"a", "b", "c"}, "f1")
            queue.update({"d"}, "f2")
        with self.queue() as queue:
            queue.update({"e"}, "f3")
        self.assertDiffed("a b c d e")

    def test_stop_with_cases_to_diff(self):
        self.add_cases("a", "f1")
        with self.assertRaises(Error), self.queue() as queue:
            # HACK mutate queue internal state
            # currently there is no easier way to stop non-empty cases_to_diff
            queue.cases_to_diff["a"] = self.get_cases("a")[0]
            raise Error("do not _process_remaining_diffs")
        self.assertTrue(queue.cases_to_diff)
        with self.queue() as queue:
            pass
        self.assertDiffed("a")

    def test_resume_after_error_in_process_remaining_diffs(self):
        self.add_cases("a b c", "f1")
        self.add_cases("d", "f2")
        with self.assertRaises(Error), self.queue() as queue:
            mock = patch.object(queue, "_process_remaining_diffs").start()
            mock.side_effect = Error("cannot process remaining diffs")
            queue.update({"a", "b", "c"}, "f1")
        queue.pool.kill()  # simulate end process
        with self.queue() as queue:
            queue.update({"d"}, "f2")
        self.assertDiffed("a b c d")

    def test_defer_diff_until_all_forms_are_processed(self):
        self.add_cases("a b", "f0")
        self.add_cases("c d", "f1")
        self.add_cases("b d e", "f2")
        with self.queue() as queue:
            queue.update({"a", "b"}, "f0")
            queue.update({"c", "d"}, "f1")
            self.flush(queue)
            self.assertDiffed("a c")
            queue.update({"b", "d", "e"}, "f2")
        self.assertDiffed("a b c d e")

    @contextmanager
    def queue(self):
        log.info("init CaseDiffQueue")
        with init_state_db("test") as statedb, \
                mod.CaseDiffQueue(statedb, self.diff_cases) as queue:
            yield queue

    @staticmethod
    def flush(queue):
        pool = queue.pool
        while not pool.join(timeout=1):
            log.info('waiting on {} case diff workers'.format(len(pool)))

    def add_cases(self, case_ids, xform_ids=()):
        """Add cases with updating form ids

        `case_ids` and `form_ids` can be either a string (space-
        delimited ids) or a sequence of strings (ids).
        """
        if isinstance(case_ids, six.text_type):
            case_ids = case_ids.split()
        if isinstance(xform_ids, six.text_type):
            xform_ids = xform_ids.split()
        for case_id in case_ids:
            if case_id in self.cases:
                case = self.cases[case_id]
                for fid in xform_ids:
                    assert fid not in case.xform_ids, (fid, case)
                    case.xform_ids.append(fid)
            else:
                self.cases[case_id] = FakeCase(case_id, list(xform_ids) or [])

    def get_cases(self, case_ids):
        def get(case_id):
            try:
                case = self.cases[case_id]
                log.info("get %s", case)
            except Exception as err:
                log.info("get %s -> %s", case_id, err)
                raise
            return case
        return [get(case_id) for case_id in case_ids]

    def diff_cases(self, cases):
        log.info("diff cases %s", list(cases))
        for case in six.itervalues(cases):
            case_id = case["_id"]
            self.diffed[case_id] += 1

    def assertDiffed(self, spec):
        if not isinstance(spec, dict):
            if isinstance(spec, six.text_type):
                spec = spec.split()
            spec = {c: 1 for c in spec}
        self.assertEqual(dict(self.diffed), spec)

    @contextmanager
    def get_cases_failure(self):
        """Raise error on CaseAccessorCouch.get_cases(...)

        Assumes `CaseAccessorCouch.get_cases` has been patched with
        `self.get_cases`.
        """
        with self.expected_error(), patch.object(self, "cases") as couch:
            couch.__getitem__.side_effect = Error("COUCH IS DOWN!")
            yield

    @contextmanager
    def diff_cases_failure(self):
        """Raise error on self.diff_cases(...)"""
        with self.expected_error(), patch.object(self, "diffed") as diffed:
            diffed.__setitem__.side_effect = Error("FAILED TO DIFF!")
            yield

    @contextmanager
    def expected_error(self):
        with silence_expected_errors(), self.assertRaises(Error):
            yield


@attr.s
class FakeCase(object):

    _id = attr.ib()
    xform_ids = attr.ib(factory=list)
    actions = attr.ib(factory=list)

    @property
    def case_id(self):
        return self._id

    def to_json(self):
        return {f.name: getattr(self, f.name) for f in attr.fields(type(self))}


class Error(Exception):
    pass


@contextmanager
def silence_expected_errors():
    """Prevent print expected error to stderr

    not sure why it is not captured by nose
    """
    def print_unexpected(context, type, value, tb):
        if type == Error:
            log.error(context, exc_info=(type, value, tb))
        else:
            print_exception(context, type, value, tb)

    hub = gevent.get_hub()
    print_exception = hub.print_exception
    with patch.object(hub, "print_exception", print_unexpected):
        yield
