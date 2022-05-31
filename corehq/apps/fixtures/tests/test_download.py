from testil import eq

from .. import download as mod
from ..models import FixtureDataType, FixtureTypeField


def test_get_indexed_field_numbers():
    table = create_index_tables()[1]
    eq(mod.get_indexed_field_numbers([table], 5), {0, 2, 4})


def test_get_indexed_field_numbers_for_multiple_tables():
    tables = create_index_tables()
    eq(mod.get_indexed_field_numbers(tables, 7), {0, 1, 2, 4, 6})


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
        FixtureDataType(fields=[
            FixtureTypeField(field_name="a1", properties=[], is_indexed=True),
            FixtureTypeField(field_name="a2", properties=[], is_indexed=True),
            FixtureTypeField(field_name="a3", properties=[], is_indexed=False),
        ]),
        FixtureDataType(fields=[
            FixtureTypeField(field_name="b1", properties=[], is_indexed=True),
            FixtureTypeField(field_name="b2", properties=[], is_indexed=False),
            FixtureTypeField(field_name="b3", properties=[], is_indexed=True),
            FixtureTypeField(field_name="b4", properties=[], is_indexed=False),
            FixtureTypeField(field_name="b5", properties=[], is_indexed=True),
        ]),
        FixtureDataType(fields=[
            FixtureTypeField(field_name="c1", properties=[], is_indexed=False),
            FixtureTypeField(field_name="c2", properties=[], is_indexed=False),
            FixtureTypeField(field_name="c3", properties=[], is_indexed=False),
            FixtureTypeField(field_name="c4", properties=[], is_indexed=False),
            FixtureTypeField(field_name="c5", properties=[], is_indexed=False),
            FixtureTypeField(field_name="c6", properties=[], is_indexed=False),
            FixtureTypeField(field_name="c7", properties=[], is_indexed=True),
        ]),
    ]
