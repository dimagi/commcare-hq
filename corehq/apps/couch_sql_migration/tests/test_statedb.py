from __future__ import absolute_import
from __future__ import unicode_literals

import re

from sqlalchemy.exc import OperationalError
from testil import assert_raises, eq, tempdir

from corehq.apps.tzmigration.timezonemigration import FormJsonDiff as JsonDiff

from ..statedb import (
    Counts,
    ResumeError,
    delete_state_db,
    diff_doc_id_idx,
    init_state_db,
)


def setup_module():
    global _tmp, state_dir
    _tmp = tempdir()
    state_dir = _tmp.__enter__()


def teardown_module():
    _tmp.__exit__(None, None, None)


def teardown():
    delete_state_db("test", state_dir)


def init_db():
    return init_state_db("test", state_dir)


def test_db_unique_id():
    with init_db() as db:
        uid = db.unique_id
        assert re.search(r"\d{8}-\d{6}.\d{6}", uid), uid

    with init_db() as db:
        eq(db.unique_id, uid)

    delete_state_db("test", state_dir)
    with init_db() as db:
        assert db.unique_id != uid, uid


def test_problem_forms():
    with init_db() as db:
        db.add_problem_form("abc")

    with init_db() as db:
        db.add_problem_form("def")
        eq(set(db.iter_problem_forms()), {"abc", "def"})


def test_no_action_case_forms():
    with init_db() as db:
        db.add_no_action_case_form("abc")

    with init_db() as db:
        eq(db.get_no_action_case_forms(), {"abc"})

        # verify that memoized result is cleared on add
        db.add_no_action_case_form("def")
        eq(db.get_no_action_case_forms(), {"abc", "def"})


def test_resume_state():
    with init_db() as db:
        eq(db.pop_resume_state("test", []), [])
        db.set_resume_state("test", ["abc", "def"])

    with init_db() as db:
        eq(db.pop_resume_state("test", []), ["abc", "def"])

    # simulate resume without save
    with init_db() as db:
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
