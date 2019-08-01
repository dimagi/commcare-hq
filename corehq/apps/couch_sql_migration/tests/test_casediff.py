from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
try:
    from inspect import signature
except ImportError:
    from funcsigs import signature  # TODO remove after Python 3 upgrade

import attr
import gevent
import six
from django.test import SimpleTestCase
from gevent.event import Event
from gevent.queue import Queue
from mock import patch
from testil import Config, tempdir

from corehq.apps.tzmigration.timezonemigration import FormJsonDiff
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference

from .. import casediff as mod
from ..statedb import delete_state_db, init_state_db, StateDB

log = logging.getLogger(__name__)


@patch.object(mod.CaseDiffQueue, "BATCH_SIZE", 2)
@patch.object(mod.BatchProcessor, "MAX_RETRIES", 0)
@patch.object(gevent.get_hub(), "SYSTEM_ERROR", BaseException)
class TestCaseDiffQueue(SimpleTestCase):

    def setUp(self):
        super(TestCaseDiffQueue, self).setUp()
        self.patches = [
            patch.object(mod, "diff_cases", self.diff_cases),
            patch(
                "corehq.form_processor.backends.couch.dbaccessors.CaseAccessorCouch.get_cases",
                self.get_cases,
            ),
            patch.object(mod, "get_stock_forms_by_case_id", self.get_stock_forms),
        ]

        for patcher in self.patches:
            patcher.start()
        self.statedb = StateDB.init(":memory:")  # in-memory db for test speed
        self.cases = {}
        self.processed_forms = defaultdict(set)
        self.stock_forms = defaultdict(set)
        self.diffed = defaultdict(int)

    def tearDown(self):
        for patcher in self.patches:
            patcher.stop()
        self.statedb.close()
        super(TestCaseDiffQueue, self).tearDown()

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

    def test_case_with_unprocessed_form(self):
        self.add_cases("c", "f0 f1")
        with self.queue() as queue:
            queue.update({"c"}, "f0")
        self.assertDiffed("c")

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
            queue.flush()
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

    def test_num_diffed_cases_on_resume(self):
        self.add_cases("a b c", "f1")
        self.add_cases("d", "f2")
        # simulate a single call to couch failing
        with self.queue() as queue:
            queue.update({"a", "b", "c"}, "f1")
        self.assertEqual(queue.num_diffed_cases, 3)
        with self.queue() as queue:
            queue.update({"d"}, "f2")
        self.assertEqual(queue.num_diffed_cases, 4)

    def test_diff_cases_failure(self):
        self.add_cases("a", "f1")
        self.add_cases("b", "f2")
        with self.queue() as queue, self.diff_cases_failure():
            queue.update({"a"}, "f1")
            queue.flush()
        with self.queue() as queue:
            queue.update({"b"}, "f2")
        self.assertDiffed("a b")

    def test_stop_with_cases_to_diff(self):
        self.add_cases("a", "f1")
        with self.assertRaises(Error), self.queue() as queue:
            # HACK mutate queue internal state
            # currently there is no easier way to stop non-empty cases_to_diff
            queue.cases_to_diff["a"] = self.get_cases("a")[0]
            raise Error("do not process_remaining_diffs")
        self.assertTrue(queue.cases_to_diff)
        with self.queue() as queue:
            pass
        self.assertDiffed("a")

    def test_resume_after_error_in_process_remaining_diffs(self):
        self.add_cases("a", "f1")
        self.add_cases("b", "f2")
        with self.assertRaises(Error), self.queue() as queue:
            mock = patch.object(queue, "process_remaining_diffs").start()
            mock.side_effect = Error("cannot process remaining diffs")
            queue.update({"a"}, "f1")
        queue.pool.kill()  # simulate end process
        with self.queue() as queue:
            queue.update({"b"}, "f2")
        self.assertDiffed("a b")

    def test_defer_diff_until_all_forms_are_processed(self):
        self.add_cases("a b", "f0")
        self.add_cases("c d", "f1")
        self.add_cases("b d e", "f2")
        with self.queue() as queue:
            queue.update({"a", "b"}, "f0")
            queue.update({"c", "d"}, "f1")
            queue.flush(complete=False)
            self.assertDiffed("a c")
            queue.update({"b", "d", "e"}, "f2")
        self.assertDiffed("a b c d e")

    def test_unexpected_case_update_scenario_1(self):
        self.add_cases("a b", "f0")
        with self.queue() as queue:
            queue.update({"a", "b"}, "f0")
            queue.flush(complete=False)
            self.assertDiffed("a b")
            queue.update({"a"}, "f1")  # unexpected update
        self.assertDiffed({"a": 2, "b": 1})

    def test_unexpected_case_update_scenario_2(self):
        self.add_cases("a", "f0")
        self.add_cases("b", "f1")
        with self.queue() as queue:
            queue.update({"a", "b"}, "f0")  # unexpected update first time b is seen
            queue.flush(complete=False)
            self.assertDiffed("a b")
            queue.update({"b"}, "f1")
        self.assertDiffed({"a": 1, "b": 2})

    def test_missing_couch_case(self):
        self.add_cases("found", "form")
        with self.queue() as queue:
            queue.update({"miss", "found"}, "form")
        self.assertDiffed("found")
        missing = queue.statedb.get_missing_doc_ids("CommCareCase-couch")
        self.assertEqual(missing, {"miss"})

    def test_case_action_with_null_xform_id(self):
        self.add_cases("a", actions=[FakeAction(None), FakeAction("f0")])
        self.add_cases("b c", "f1")
        with self.queue() as queue:
            queue.update({"a"}, "f0")
            queue.update(["b", "c"], "f1")
            queue.flush(complete=False)
            self.assertDiffed("a b c")

    def test_case_with_stock_forms(self):
        self.add_cases("a", "f0", stock_forms="f1")
        self.add_cases("b c", "f2")
        with self.queue() as queue:
            queue.update({"a"}, "f0")
            queue.update(["b", "c"], "f2")
            queue.flush(complete=False)
            self.assertDiffed("b c")
            queue.update({"a"}, "f1")
            queue.flush(complete=False)
            self.assertDiffed("a b c")

    def test_case_with_many_forms(self):
        self.add_cases("a", ["f%s" % n for n in range(25)])
        self.add_cases("b c d", "f2")
        with self.queue() as queue:
            queue.update({"a"}, "f0")
            queue.update(["b", "c", "d"], "f2")
            queue.flush(complete=False)
            self.assertDiffed("b c d")
            self.assertNotIn("a", queue.cases)
            for n in range(1, 25):
                queue.update({"a"}, "f%s" % n)
            queue.flush(complete=False)
            self.assertDiffed("a b c d")

    def test_resume_on_case_with_many_forms(self):
        self.add_cases("a", ["f%s" % n for n in range(25)])
        self.add_cases("b c d", "f2")
        with self.assertRaises(Error), self.queue() as queue:
            queue.update({"a"}, "f0")
            queue.update(["b", "c", "d"], "f2")
            queue.flush(complete=False)
            mock = patch.object(queue, "process_remaining_diffs").start()
            mock.side_effect = Error("cannot process remaining diffs")
        self.assertDiffed("b c d")
        queue.pool.kill()  # simulate end process
        with self.queue() as queue:
            queue.flush(complete=False)
            self.assertNotIn("a", queue.cases)
            for n in range(1, 25):
                queue.update({"a"}, "f%s" % n)
            queue.flush(complete=False)
            self.assertDiffed("a b c d")

    def test_cases_cache_max_size(self):
        self.add_cases("a b c d e f", ["f0", "f1"])
        patch_max_cases = patch.object(mod.CaseDiffQueue, "MAX_MEMORIZED_CASES", 4)
        with patch_max_cases, self.queue() as queue:
            queue.update({"a", "b", "c", "d", "e", "f"}, "f0")
            queue.flush(complete=False)
            self.assertEqual(len(queue.cases), 4, queue.cases)
            self.assertDiffed([])
            queue.update({"a", "b", "c", "d", "e", "f"}, "f1")
        self.assertDiffed("a b c d e f")

    def test_cases_lru_cache(self):
        # forms fa-ff update corresponding cases
        for case_id in "abcdef":
            self.add_cases(case_id, "f%s" % case_id)
        # forms f1-f5 update case a
        for i in range(1, 6):
            self.add_cases("a", "f%s" % i)
        self.add_cases("a b c d e f", "fx")
        patch_max_cases = patch.object(mod.CaseDiffQueue, "MAX_MEMORIZED_CASES", 4)
        with patch_max_cases, self.queue() as queue:
            for i, case_id in enumerate("abcdef"):
                queue.update(case_id, "f%s" % case_id)
                if i > 0:
                    # keep "a" fresh in the LRU cache
                    queue.update("a", "f%s" % i)
            queue.flush(complete=False)
            self.assertIn("a", queue.cases)
            self.assertNotIn("b", queue.cases)
            self.assertNotIn("c", queue.cases)
            self.assertDiffed([])
            queue.update({"a", "b", "c", "d", "e", "f"}, "fx")
        self.assertDiffed("a b c d e f")

    def test_case_with_many_unprocessed_forms(self):
        self.add_cases("a", ["f%s" % n for n in range(25)])
        self.add_cases("b c d", "f2")
        with self.queue() as queue:
            queue.update({"a"}, "f0")
            queue.update(["b", "c", "d"], "f2")
        self.assertDiffed("a b c d")

    def test_status_logger(self):
        event = Event()
        queue = mod.CaseDiffQueue(None, status_interval=0.00001)
        with patch.object(queue, "log_status") as log_status:
            log_status.side_effect = lambda x: event.set()
            stop = queue.run_status_logger()
            self.assertTrue(event.wait(timeout=5), "queue.log_status() not called")
            stop()
        self.assertGreater(log_status.call_count, 0)

    @contextmanager
    def queue(self):
        log.info("init CaseDiffQueue")
        with mod.CaseDiffQueue(self.statedb) as queue:
            yield queue

    def add_cases(self, case_ids, xform_ids=(), actions=(), stock_forms=()):
        """Add cases with updating form ids

        `case_ids` and `form_ids` can be either a string (space-
        delimited ids) or a sequence of strings (ids).
        """
        if isinstance(case_ids, six.text_type):
            case_ids = case_ids.split()
        if isinstance(xform_ids, six.text_type):
            xform_ids = xform_ids.split()
        if isinstance(stock_forms, six.text_type):
            stock_forms = stock_forms.split()
        for case_id in case_ids:
            if case_id in self.cases:
                case = self.cases[case_id]
            else:
                case = self.cases[case_id] = FakeCase(case_id)
            for fid in xform_ids:
                assert fid not in case.xform_ids, (fid, case)
                case.xform_ids.append(fid)
            case.actions.extend(actions)
            self.stock_forms[case_id].update(stock_forms)

    def get_cases(self, case_ids):
        def get(case_id):
            try:
                case = self.cases[case_id]
                log.info("get %s", case)
            except KeyError:
                case = None
            except Exception as err:
                log.info("get %s -> %s", case_id, err)
                raise
            return case
        cases = (get(case_id) for case_id in case_ids)
        return [c for c in cases if c is not None]

    def get_stock_forms(self, case_ids):
        return dict(self.stock_forms)

    def diff_cases(self, cases, statedb):
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


@patch.object(gevent.get_hub(), "SYSTEM_ERROR", BaseException)
class TestCaseDiffProcess(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestCaseDiffProcess, cls).setUpClass()
        cls.tmp = tempdir()
        cls.state_dir = cls.tmp.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.__exit__(None, None, None)
        super(TestCaseDiffProcess, cls).tearDownClass()

    def tearDown(self):
        delete_state_db("test", self.state_dir)
        super(TestCaseDiffProcess, self).tearDown()

    def test_process(self):
        with self.process() as proc:
            self.assertEqual(self.get_status(proc), [0, 0, 0])
            proc.update({"case1", "case2"}, "form")
            proc.enqueue({"case": "data"})
            self.assertEqual(self.get_status(proc), [2, 1, 0])

    def test_process_statedb(self):
        with self.process() as proc1:
            self.assertEqual(self.get_status(proc1), [0, 0, 0])
            proc1.enqueue({"case": "data"})
            self.assertEqual(self.get_status(proc1), [0, 1, 0])
        with self.process() as proc2:
            self.assertEqual(self.get_status(proc2), [0, 1, 0])
            proc2.enqueue({"case": "data"})
            self.assertEqual(self.get_status(proc2), [0, 2, 0])

    def test_fake_case_diff_queue_interface(self):
        tested = set()
        for name in dir(FakeCaseDiffQueue):
            if name.startswith("_"):
                continue
            tested.add(name)
            fake = getattr(FakeCaseDiffQueue, name)
            real = getattr(mod.CaseDiffQueue, name)
            self.assertEqual(signature(fake), signature(real))
        self.assertEqual(tested, {"update", "enqueue", "get_status"})

    @contextmanager
    def process(self):
        with init_state_db("test", self.state_dir) as statedb, mod.CaseDiffProcess(
            statedb,
            status_interval=1,
            queue_class=FakeCaseDiffQueue,
        ) as proc:
            yield proc

    @staticmethod
    def get_status(proc):
        def log_status(status):
            log.info("status: %s", status)
            keys = ["pending_cases", "pending_diffs", "diffed_cases"]
            assert keys == list(status), status
            queue.put([status[k] for k in keys])

        queue = Queue()
        with patch.object(mod.CaseDiffQueue, "log_status") as mock:
            mock.side_effect = log_status
            proc.request_status()
            return queue.get(timeout=5)


class FakeCaseDiffQueue(object):

    def __init__(self, statedb, status_interval=None):
        self.statedb = statedb
        self.stats = {"pending_cases": 0, "pending_diffs": 0, "diffed_cases": 0}

    def __enter__(self):
        state = self.statedb.pop_resume_state(type(self).__name__, {})
        if "stats" in state:
            self.stats = state["stats"]
        return self

    def __exit__(self, *exc_info):
        self.statedb.set_resume_state(type(self).__name__, {"stats": self.stats})

    def update(self, case_ids, form_id):
        self.stats["pending_cases"] += len(case_ids)

    def enqueue(self, case_doc):
        self.stats["pending_diffs"] += 1

    def get_status(self):
        return self.stats


@patch.object(gevent.get_hub(), "SYSTEM_ERROR", BaseException)
class TestBatchProcessor(SimpleTestCase):

    def setUp(self):
        super(TestBatchProcessor, self).setUp()
        self.proc = mod.BatchProcessor(mod.Pool())

    def test_retry_batch(self):
        def do(thing):
            tries.append(1)
            if len(tries) < 2:
                raise Error("cannot do thing the first time")
            done.append(thing)

        tries = []
        done = []
        self.proc.spawn(do, "thing")
        flush(self.proc.pool)
        self.assertEqual(len(tries), 2)
        self.assertEqual(done, ["thing"])

    def test_batch_max_retries(self):
        def do(thing):
            tries.append(1)
            raise Error("cannot do thing... ever")

        tries = []
        self.proc.spawn(do, "thing")
        with silence_expected_errors(), self.assertRaises(Error):
            flush(self.proc.pool)
        self.assertEqual(len(tries), 3)


class TestDiffCases(SimpleTestCase):

    def setUp(self):
        super(TestDiffCases, self).setUp()
        self.patches = [
            patch(
                "corehq.form_processor.backends.sql.dbaccessors.CaseAccessorSQL.get_cases",
                self.get_sql_cases,
            ),
            patch(
                "corehq.form_processor.backends.sql.dbaccessors"
                ".LedgerAccessorSQL.get_ledger_values_for_cases",
                self.get_sql_ledgers,
            ),
            patch(
                "corehq.apps.commtrack.models.StockState.objects.filter",
                self.get_stock_states,
            ),
            patch(
                "corehq.form_processor.backends.couch.processor"
                ".FormProcessorCouch.hard_rebuild_case",
                self.hard_rebuild_case,
            ),
        ]

        for patcher in self.patches:
            patcher.start()
        self.statedb = StateDB.init(":memory:")
        self.sql_cases = {}
        self.sql_ledgers = {}
        self.couch_cases = {}
        self.couch_ledgers = {}

    def tearDown(self):
        for patcher in self.patches:
            patcher.stop()
        self.statedb.close()
        super(TestDiffCases, self).tearDown()

    def test_clean(self):
        self.add_case("a")
        mod.diff_cases(self.couch_cases, self.statedb)
        self.assert_diffs()

    def test_diff(self):
        couch_json = self.add_case("a", prop=1)
        couch_json["prop"] = 2
        mod.diff_cases(self.couch_cases, self.statedb)
        self.assert_diffs([Diff("a", path=["prop"], old=2, new=1)])

    def test_replace_diff(self):
        self.add_case("a", prop=1)
        different_cases = deepcopy(self.couch_cases)
        different_cases["a"]["prop"] = 2
        mod.diff_cases(different_cases, self.statedb)
        self.assert_diffs([Diff("a", path=["prop"], old=2, new=1)])
        mod.diff_cases(self.couch_cases, self.statedb)
        self.assert_diffs()

    def test_replace_ledger_diff(self):
        self.add_case("a")
        stock = self.add_ledger("a", x=1)
        stock.values["x"] = 2
        mod.diff_cases(self.couch_cases, self.statedb)
        self.assert_diffs([Diff("a/stock/a", "stock state", path=["x"], old=2, new=1)])
        stock.values["x"] = 1
        mod.diff_cases(self.couch_cases, self.statedb)
        self.assert_diffs()

    def assert_diffs(self, expected=None):
        actual = [
            Diff(diff.doc_id, diff.kind, *diff.json_diff)
            for diff in self.statedb.get_diffs()
        ]
        self.assertEqual(actual, expected or [])

    def add_case(self, case_id, **props):
        assert case_id not in self.sql_cases, self.sql_cases[case_id]
        assert case_id not in self.couch_cases, self.couch_cases[case_id]
        props.setdefault("doc_type", "CommCareCase")
        self.sql_cases[case_id] = Config(
            case_id=case_id,
            props=props,
            to_json=lambda: dict(props, case_id=case_id),
            is_deleted=False,
        )
        self.couch_cases[case_id] = couch_case = dict(props, case_id=case_id)
        return couch_case

    def add_ledger(self, case_id, **values):
        ref = UniqueLedgerReference(case_id, "stock", case_id)
        self.sql_ledgers[case_id] = Config(
            ledger_reference=ref,
            values=values,
            to_json=lambda: dict(values, ledger_reference=ref.as_id()),
        )
        couch_values = dict(values)
        stock = Config(
            ledger_reference=ref,
            values=couch_values,
            to_json=lambda: dict(couch_values, ledger_reference=ref.as_id()),
        )
        self.couch_ledgers[case_id] = stock
        return stock

    def get_sql_cases(self, case_ids):
        return [self.sql_cases[c] for c in case_ids]

    def get_sql_ledgers(self, case_ids):
        ledgers = self.sql_ledgers
        return [ledgers[c] for c in case_ids if c in ledgers]

    def get_stock_states(self, case_id__in):
        ledgers = self.couch_ledgers
        return [ledgers[c] for c in case_id__in if c in ledgers]

    def hard_rebuild_case(self, domain, case_id, *args, **kw):
        return Config(to_json=lambda: self.couch_cases[case_id])


@attr.s
class Diff(object):
    doc_id = attr.ib()
    kind = attr.ib(default="CommCareCase")
    type = attr.ib(default="diff")
    path = attr.ib(factory=list)
    old = attr.ib(default=None)
    new = attr.ib(default=None)


@attr.s
class FakeCase(object):

    _id = attr.ib()
    xform_ids = attr.ib(factory=list)
    actions = attr.ib(factory=list)

    @property
    def case_id(self):
        return self._id

    def to_json(self):
        data = {n: getattr(self, n) for n in ["_id", "xform_ids"]}
        data["actions"] = [a.to_json() for a in self.actions]
        return data


@attr.s
class FakeAction(object):

    xform_id = attr.ib()

    def to_json(self):
        return {"xform_id": self.xform_id}


DIFFS = [FormJsonDiff("diff", ["prop"], "old", "new")]


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


def flush(pool):
    while not pool.join(timeout=1):
        log.info('waiting on {} case diff workers'.format(len(pool)))
