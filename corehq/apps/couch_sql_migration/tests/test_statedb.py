from __future__ import absolute_import
from __future__ import unicode_literals

from testil import eq

from ..statedb import Counts, init_state_db


def test_counters():
    db = init_state_db("test")
    db.increment_counter("abc", 1)
    db.add_missing_docs("abc", ["doc1"])
    db.increment_counter("def", 2)
    db.increment_counter("abc", 3)
    db.add_missing_docs("abc", ["doc2", "doc4"])
    eq(db.get_doc_counts(), {
        "abc": Counts(4, 3),
        "def": Counts(2, 0),
    })
