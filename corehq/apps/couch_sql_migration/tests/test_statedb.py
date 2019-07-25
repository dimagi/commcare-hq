from __future__ import absolute_import
from __future__ import unicode_literals

import pickle
import re

from sqlalchemy.exc import OperationalError
from nose.tools import with_setup
from testil import assert_raises, Config, eq, tempdir

from corehq.apps.tzmigration.timezonemigration import FormJsonDiff as JsonDiff

from ..statedb import (
    Counts,
    delete_state_db,
    diff_doc_id_idx,
    init_state_db,
    ResumeError,
    StateDB,
)


def setup_module():
    global _tmp, state_dir
    _tmp = tempdir()
    state_dir = _tmp.__enter__()


def teardown_module():
    _tmp.__exit__(None, None, None)


def init_db(memory=True):
    if memory:
        return StateDB.init(":memory:")
    return init_state_db("test", state_dir)


def delete_db():
    delete_state_db("test", state_dir)


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
        eq(list(db.iter_cases_with_unprocessed_forms()), ["a", "b", "c"])


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


@with_setup(teardown=delete_db)
def test_resume_state():
    with init_db(memory=False) as db:
        eq(db.pop_resume_state("test", []), [])
        db.set_resume_state("test", ["abc", "def"])

    with init_db(memory=False) as db:
        eq(db.pop_resume_state("test", []), ["abc", "def"])

    # simulate resume without save
    with init_db(memory=False) as db:
        with assert_raises(ResumeError):
            db.pop_resume_state("test", [])


def test_unexpected_diffs():
    with init_db() as db:
        db.add_diffs("kind", "abc", [JsonDiff("type", "path", "old", "new")])
        db.add_diffs("kind", "def", [JsonDiff("type", "path", "old", "new")])
        db.add_diffs("kind", "xyz", [JsonDiff("type", "path", "old", "new")])
        db.add_unexpected_diff("abc")
        db.add_unexpected_diff("def")
        db.add_unexpected_diff("abc")
        eq(list(db.iter_unexpected_diffs()), ["abc", "def"])


def test_counters():
    with init_db() as db:
        db.increment_counter("abc", 1)
        db.add_missing_docs("abc", ["doc1"])
        db.increment_counter("def", 2)
        db.increment_counter("abc", 3)
        db.add_missing_docs("abc", ["doc2", "doc4"])
        eq(db.get_doc_counts(), {
            "abc": Counts(4, 3),
            "def": Counts(2, 0),
        })


def test_diff_doc_id_idx_exists():
    msg = re.compile("index diff_doc_id_idx already exists")
    with init_db() as db, assert_raises(OperationalError, msg=msg):
        diff_doc_id_idx.create(db.engine)


@with_setup(teardown=delete_db)
def test_pickle():
    with init_db(memory=False) as db:
        other = pickle.loads(pickle.dumps(db))
        assert isinstance(other, type(db)), (other, db)
        assert other is not db
        eq(db.unique_id, other.unique_id)
