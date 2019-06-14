from __future__ import absolute_import
from __future__ import unicode_literals

from testil import eq

from ..statedb import Counts, delete_state_db, init_state_db


def teardown():
    delete_state_db("test")


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

