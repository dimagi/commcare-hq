from testil import eq

from ..const import SpecialCaseProperty


def test_defaults():
    prop = SpecialCaseProperty("@owner_id", "owner_id")
    eq(prop.key, "@owner_id")
    eq(prop.doc_key, "owner_id")
    eq(prop.sort_property, "owner_id")
    eq(prop.case_property, "owner_id")
    eq(prop.default, None)
    eq(prop.value_getter({}), None)
    eq(prop.value_getter({"owner_id": 42}), 42)


def test_sort_property():
    prop = SpecialCaseProperty('@case_type', 'type', 'type.exact')
    eq(prop.sort_property, "type.exact")
    eq(prop.case_property, "type")


def test_case_property():
    prop = SpecialCaseProperty('@case_id', '_id', case_property="case_id")
    eq(prop.sort_property, "_id")
    eq(prop.case_property, "case_id")


def test_default_value_getter():
    prop = SpecialCaseProperty("external_id", "external_id", default="")
    eq(prop.value_getter({"external_id": 1}), 1)
    eq(prop.value_getter({}), "")


def test_custom_value_getter():
    prop = SpecialCaseProperty('@status', 'closed',
        value_getter=lambda doc: 'closed' if doc.get('closed') else 'open')
    eq(prop.value_getter({}), "open")
    eq(prop.value_getter({"closed": ""}), "open")
    eq(prop.value_getter({"closed": "true"}), "closed")
