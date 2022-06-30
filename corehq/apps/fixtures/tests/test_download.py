from testil import eq

from .. import download as mod
from ..models import LookupTable, TypeField


def test_get_indexed_field_numbers():
    table = create_index_tables()[1]
    eq(mod.get_indexed_field_numbers([table]), {0, 2, 4})


def test_get_indexed_field_numbers_for_multiple_tables():
    tables = create_index_tables()
    eq(mod.get_indexed_field_numbers(tables), {0, 1, 2, 4, 6})


def test_iter_types_headers():
    eq(list(mod.iter_types_headers(7, {0, 3, 6})), [
        "field 1",
        "field 1: is_indexed?",
        "field 2",
        "field 3",
        "field 4",
        "field 4: is_indexed?",
        "field 5",
        "field 6",
        "field 7",
        "field 7: is_indexed?",
    ])


def create_index_tables():
    return [
        LookupTable(fields=[
            TypeField(name="a1", is_indexed=True),
            TypeField(name="a2", is_indexed=True),
            TypeField(name="a3"),
        ]),
        LookupTable(fields=[
            TypeField(name="b1", is_indexed=True),
            TypeField(name="b2"),
            TypeField(name="b3", is_indexed=True),
            TypeField(name="b4"),
            TypeField(name="b5", is_indexed=True),
        ]),
        LookupTable(fields=[
            TypeField(name="c1"),
            TypeField(name="c2"),
            TypeField(name="c3"),
            TypeField(name="c4"),
            TypeField(name="c5"),
            TypeField(name="c6"),
            TypeField(name="c7", is_indexed=True),
        ]),
    ]
