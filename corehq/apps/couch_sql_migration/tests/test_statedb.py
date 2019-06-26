from __future__ import absolute_import
from __future__ import unicode_literals

import re

from testil import assert_raises, eq

from ..statedb import Counts, delete_state_db, init_state_db, ResumeError


def teardown():
    delete_state_db("test")


def test_db_unique_id():
    with init_state_db("test") as db:
        uid = db.unique_id
        assert re.search(r"\d{8}-\d{6}.\d{6}", uid), uid

    with init_state_db("test") as db:
        eq(db.unique_id, uid)

    delete_state_db("test")
    with init_state_db("test") as db:
        assert db.unique_id != uid, uid


def test_problem_forms():
    with init_state_db("test") as db:
        db.add_problem_form("abc")

    with init_state_db("test") as db:
        db.add_problem_form("def")
        eq(set(db.iter_problem_forms()), {"abc", "def"})


def test_no_action_case_forms():
    with init_state_db("test") as db:
        db.add_no_action_case_form("abc")

    with init_state_db("test") as db:
        eq(db.get_no_action_case_forms(), {"abc"})

        # verify that memoized result is cleared on add
        db.add_no_action_case_form("def")
        eq(db.get_no_action_case_forms(), {"abc", "def"})


def test_resume_state():
    with init_state_db("test") as db:
        eq(db.pop_resume_state("test", []), [])
        db.set_resume_state("test", ["abc", "def"])

    with init_state_db("test") as db:
        eq(db.pop_resume_state("test", []), ["abc", "def"])

    # simulate resume without save
    with init_state_db("test") as db:
        with assert_raises(ResumeError):
            db.pop_resume_state("test", [])


def test_counters():
    with init_state_db("test") as db:
        db.increment_counter("abc", 1)
        db.add_missing_docs("abc", ["doc1"])
        db.increment_counter("def", 2)
        db.increment_counter("abc", 3)
        db.add_missing_docs("abc", ["doc2", "doc4"])
        eq(db.get_doc_counts(), {
            "abc": Counts(4, 3),
            "def": Counts(2, 0),
        })
