import pickle
import os
import re

from nose.tools import with_setup
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import SingletonThreadPool
from testil import Config, assert_raises, eq, tempdir

from corehq.apps.tzmigration.timezonemigration import FormJsonDiff as JsonDiff

from ..statedb import (
    Counts,
    ResumeError,
    StateDB,
    _get_state_db_filepath,
    delete_state_db,
    init_state_db,
    open_state_db,
)
from .. import statedb as mod


def setup_module():
    global _tmp, state_dir
    _tmp = tempdir()
    state_dir = _tmp.__enter__()


def teardown_module():
    _tmp.__exit__(None, None, None)


def init_db(name="test", memory=True):
    if memory:
        return StateDB.init(name, ":memory:")
    return init_state_db(name, state_dir)


def delete_db(name="test"):
    delete_state_db(name, state_dir)


def test_file_connection_pool():
    # SingletonThreadPool docs state that "it is generally used only
    # for test scenarios using a SQLite ``:memory:`` database and is
    # not recommended for production use."
    with init_db(memory=False) as db:
        assert not isinstance(db.engine.pool, SingletonThreadPool), db.engine.pool


@with_setup(teardown=delete_db)
def test_db_unique_id():
    with init_db(memory=False) as db:
        uid = db.unique_id
        assert re.search(r"\d{8}-\d{6}.\d{6}", uid), uid

    with init_db(memory=False) as db:
        eq(db.unique_id, uid)

    delete_db()
    with init_db(memory=False) as db:
        assert db.unique_id != uid, uid


@with_setup(teardown=delete_db)
def test_open_state_db():
    assert not os.path.exists(_get_state_db_filepath("test", state_dir))
    with assert_raises(mod.Error):
        open_state_db("test", state_dir)
    with init_db(memory=False) as db:
        uid = db.unique_id
        eq(db.get("key"), None)
        db.set("key", 2)
    with open_state_db("test", state_dir) as db:
        eq(db.unique_id, uid)
        eq(db.get_doc_counts(), {})
        eq(db.get("key"), 2)
        with assert_raises(OperationalError):
            db.set("key", 3)


def test_update_cases():
    with init_db() as db:
        result = db.update_cases([
            Config(id="a", total_forms=2, processed_forms=1),
            Config(id="b", total_forms=2, processed_forms=1),
            Config(id="c", total_forms=2, processed_forms=1),
        ])
        eq(sorted(result), [
            ("a", 2, 1),
            ("b", 2, 1),
            ("c", 2, 1),
        ])
        result = db.update_cases([
            Config(id="b", total_forms=1, processed_forms=3),
            Config(id="c", total_forms=3, processed_forms=1),
            Config(id="d", total_forms=2, processed_forms=1),
        ])
        eq(sorted(result), [
            ("b", 2, 4),
            ("c", 3, 2),
            ("d", 2, 1),
        ])


def test_add_processed_forms():
    with init_db() as db:
        db.update_cases([
            Config(id="a", total_forms=2, processed_forms=1),
            Config(id="b", total_forms=2, processed_forms=1),
            Config(id="c", total_forms=4, processed_forms=1),
        ])
        result = db.add_processed_forms({"b": 1, "c": 2, "d": 2})
        eq(sorted(result), [
            ("b", 2, 2),
            ("c", 4, 3),
            ("d", None, None),
        ])


def test_iter_cases_with_unprocessed_forms():
    with init_db() as db:
        db.update_cases([
            Config(id="a", total_forms=2, processed_forms=1),
            Config(id="b", total_forms=2, processed_forms=1),
            Config(id="c", total_forms=4, processed_forms=1),
        ])
        eq(list(db.iter_cases_with_unprocessed_forms()),
            [("a", 2), ("b", 2), ("c", 4)])


def test_get_forms_count():
    with init_db() as db:
        db.update_cases([
            Config(id="a", total_forms=2, processed_forms=1),
            Config(id="b", total_forms=2, processed_forms=3),
        ])
        eq(db.get_forms_count("a"), 2)
        eq(db.get_forms_count("b"), 2)
        eq(db.get_forms_count("c"), 0)


def test_case_diff_lifecycle():
    with init_db() as db:
        case_ids = ["a", "b", "c"]
        db.add_cases_to_diff(case_ids)
        db.add_cases_to_diff(["d"])
        db.add_cases_to_diff(["d"])  # add again should not error
        db.add_cases_to_diff([])  # no ids should not error
        db.add_diffed_cases(case_ids)
        eq(list(db.iter_undiffed_case_ids()), ["d"])
        eq(db.count_undiffed_cases(), 1)
        db.add_diffed_cases(case_ids)  # add again should not error
        db.add_diffed_cases([])  # no ids should not error


@with_setup(teardown=delete_db)
def test_problem_forms():
    with init_db(memory=False) as db:
        db.add_problem_form("abc")

    with init_db(memory=False) as db:
        db.add_problem_form("def")
        eq(set(db.iter_problem_forms()), {"abc", "def"})


@with_setup(teardown=delete_db)
def test_no_action_case_forms():
    with init_db(memory=False) as db:
        db.add_no_action_case_form("abc")

    with init_db(memory=False) as db:
        eq(db.get_no_action_case_forms(), {"abc"})

        # verify that memoized result is cleared on add
        db.add_no_action_case_form("def")
        eq(db.get_no_action_case_forms(), {"abc", "def"})


def test_duplicate_no_action_case_form():
    with init_db() as db:
        db.add_no_action_case_form("abc")
        db.add_no_action_case_form("abc")  # should not raise


@with_setup(teardown=delete_db)
def test_resume_state():
    with init_db(memory=False) as db:
        with db.pop_resume_state("test", []) as value:
            eq(value, [])
        db.set_resume_state("test", ["abc", "def"])

    with init_db(memory=False) as db, assert_raises(ValueError):
        with db.pop_resume_state("test", []) as value:
            # error in context should not cause state to be lost
            raise ValueError(value)

    with init_db(memory=False) as db:
        with db.pop_resume_state("test", []) as value:
            eq(value, ["abc", "def"])

    # simulate resume without save
    with init_db(memory=False) as db:
        with assert_raises(ResumeError):
            with db.pop_resume_state("test", []):
                pass


def test_case_ids_with_diffs():
    with init_db() as db:
        db.replace_case_diffs([
            ("CommCareCase", "case-1", [make_diff(0)]),
            ("stock state", "case-1/x/y", [make_diff(1)]),
            ("CommCareCase", "case-2", [make_diff(2)]),
            ("stock state", "case-2/x/y", [make_diff(3)]),
            ("stock state", "case-2/x/z", [make_diff(5)]),
        ])
        eq(db.count_case_ids_with_diffs(), 2)
        eq(set(db.iter_case_ids_with_diffs()), {"case-1", "case-2"})


def test_replace_case_diffs():
    with init_db() as db:
        case_id = "865413246874321"
        # add old diffs
        db.replace_case_diffs([
            ("CommCareCase", case_id, [make_diff(0)]),
            ("stock state", case_id + "/x/y", [make_diff(1)]),
            ("CommCareCase", "unaffected", [make_diff(2)]),
            ("stock state", "unaffected/x/y", [make_diff(3)]),
            ("CommCareCase", "stock-only", [make_diff(4)]),
            ("stock state", "stock-only/x/y", [make_diff(5)]),
            ("CommCareCase", "gone", [make_diff(4)]),
            ("stock state", "gone/x/y", [make_diff(5)]),
        ])
        # add new diffs
        db.replace_case_diffs([
            ("CommCareCase", case_id, [make_diff(6)]),
            ("stock state", case_id + "/y/z", [make_diff(7)]),
            ("stock state", "stock-only/y/z", [make_diff(8)]),
            ("CommCareCase", "gone", []),
            ("stock state", "gone/x/y", []),
        ])
        eq(
            {(d.kind, d.doc_id, hashable(d.json_diff)) for d in db.get_diffs()},
            {(kind, doc_id, hashable(make_diff(x))) for kind, doc_id, x in [
                ("CommCareCase", "unaffected", 2),
                ("stock state", "unaffected/x/y", 3),
                ("CommCareCase", case_id, 6),
                ("stock state", case_id + "/y/z", 7),
                ("stock state", "stock-only/y/z", 8),
            ]},
        )


def test_save_form_diffs():
    def doc(name):
        return {"doc_type": "XFormInstance", "_id": "test", "name": name}

    def check_diffs(expect_count):
        diffs = db.get_diffs()
        eq(len(diffs), expect_count, [d.json_diff for d in diffs])

    with init_db() as db:
        db.save_form_diffs(doc("a"), doc("b"))
        db.save_form_diffs(doc("a"), doc("c"))
        check_diffs(1)
        db.save_form_diffs(doc("a"), doc("d"))
        check_diffs(1)
        db.save_form_diffs(doc("a"), doc("a"))
        check_diffs(0)


def test_counters():
    with init_db() as db:
        db.add_missing_docs("abc", ["doc1"])
        db.add_missing_docs("abc", ["doc2", "doc4"])
        db.replace_case_diffs([("abc", "doc5", [make_diff(5)])])
        chg = mod.Change(kind=None, doc_id=None, reason="because", **make_diff(6)._asdict())
        db.replace_case_changes([("def", "doc5", [chg])])
        db.set_counter("abc", 4)
        db.set_counter("def", 2)
        eq(db.get_doc_counts(), {
            "abc": Counts(total=4, diffs=1, missing=3),
            "def": Counts(total=2, changes=1),
        })


@with_setup(teardown=delete_db)
def test_pickle():
    with init_db(memory=False) as db:
        other = pickle.loads(pickle.dumps(db))
        assert isinstance(other, type(db)), (other, db)
        assert other is not db
        eq(db.unique_id, other.unique_id)


def test_clone_casediff_data_from():
    diffs = [make_diff(i) for i in range(3)]
    try:
        with init_db("main", memory=False) as main:
            uid = main.unique_id
            with init_db("cddb", memory=False) as cddb:
                main.add_problem_form("problem")
                main.save_form_diffs({"doc_type": "XFormInstance", "_id": "form"}, {})
                cddb.add_processed_forms({"case": 1})
                cddb.update_cases([
                    Config(id="case", total_forms=1, processed_forms=1),
                    Config(id="a", total_forms=2, processed_forms=1),
                    Config(id="b", total_forms=2, processed_forms=1),
                    Config(id="c", total_forms=2, processed_forms=1),
                ])
                cddb.add_missing_docs("CommCareCase", ["missing"])
                cddb.replace_case_diffs([
                    ("CommCareCase", "a", [diffs[0]]),
                    ("CommCareCase-Deleted", "b", [diffs[1]]),
                    ("stock state", "c/ledger", [diffs[2]]),
                ])
                cddb.set_counter("CommCareCase", 4)           # case, a, c, missing
                cddb.set_counter("CommCareCase-Deleted", 1)   # b
                main.add_no_action_case_form("no-action")
                main.set_resume_state("FormState", ["form"])
                cddb.set_resume_state("CaseState", ["case"])
            cddb.close()
            main.clone_casediff_data_from(cddb.db_filepath)
        main.close()

        with StateDB.open("test", main.db_filepath) as db:
            eq(list(db.iter_cases_with_unprocessed_forms()), [("a", 2), ("b", 2), ("c", 2)])
            eq(list(db.iter_problem_forms()), ["problem"])
            eq(db.get_no_action_case_forms(), {"no-action"})
            with db.pop_resume_state("CaseState", "nope") as value:
                eq(value, ["case"])
            with db.pop_resume_state("FormState", "fail") as value:
                eq(value, ["form"])
            eq(db.unique_id, uid)
    finally:
        delete_db("main")
        delete_db("cddb")


def test_clone_casediff_data_from_tables():
    from corehq.apps.tzmigration.planning import (
        PlanningForm,
        PlanningCase,
        PlanningCaseAction,
        PlanningStockReportHelper,
    )
    # Any time a model is added to this list it must be analyzed for usage
    # by the case diff process. StateDB.clone_casediff_data_from() may need
    # to be updated.
    eq(set(mod.Base.metadata.tables), {m.__tablename__ for m in [
        mod.CaseForms,
        mod.CaseToDiff,
        mod.Diff,
        mod.DiffedCase,
        mod.KeyValue,
        mod.DocCount,
        mod.DocDiffs,
        mod.DocChanges,
        mod.MissingDoc,
        mod.NoActionCaseForm,
        mod.PatchedCase,
        mod.ProblemForm,
        # models not used by couch-to-sql migration
        PlanningForm,
        PlanningCase,
        PlanningCaseAction,
        PlanningStockReportHelper,
    ]})


def test_get_set():
    with init_db() as db:
        eq(db.get("key"), None)
        eq(db.get("key", "default"), "default")
        db.set("key", True)
        eq(db.get("key"), True)


@with_setup(teardown=delete_db)
def test_migrate():
    with init_db(memory=False) as db:
        old_add_diffs = super(StateDB, db).add_diffs
        old_add_diffs("Test", "test", [make_diff(0)])
        old_add_diffs("Test", "test", [make_diff(1)])
        old_add_diffs("CommCareCase", "abc", [make_diff(2)])
        old_add_diffs("stock state", "abc/x/y", [make_diff(3)])
        old_add_diffs("stock state", "def/x/y", [make_diff(4)])
        eq(list(db.iter_diffs()), [])

    with init_db(memory=False) as db:
        eq(
            {(d.kind, d.doc_id, hashable(d.json_diff)) for d in db.iter_diffs()},
            {
                ("Test", "test", hashable(make_diff(0))),
                ("Test", "test", hashable(make_diff(1))),
                ("CommCareCase", "abc", hashable(make_diff(2))),
                ("stock state", "abc/x/y", hashable(make_diff(3))),
                ("stock state", "def/x/y", hashable(make_diff(4))),
            }
        )
        eq(len(super(StateDB, db).get_diffs()), 5)


def make_diff(id):
    return JsonDiff("type", ["data", id], "old%s" % id, "new%s" % id)


def hashable(diff):
    return diff._replace(path=tuple(diff.path))
