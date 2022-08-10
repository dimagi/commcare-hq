from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from corehq.util.test_utils import generate_cases
from corehq.util.tests.test_jsonattrs import set_json_value

from ..models import (
    Field,
    FieldList,
    FixtureItemField,
    FixtureTypeField,
    LookupTable,
    LookupTableRow,
    TypeField,
)


class TestLookupTable(TestCase):

    def test_default_domain_is_not_valid(self):
        table = LookupTable(tag="x")
        with self.assertRaises(IntegrityError):
            table.save()

    def test_default_tag_is_not_valid(self):
        table = LookupTable(domain="test")
        with self.assertRaises(IntegrityError):
            table.save()

    def test_fields(self):
        table = LookupTable(domain="test", tag="x", fields=[TypeField("vera")])
        self.assertEqual(table.fields[0].name, "vera")
        self.assertEqual(table.fields[0].properties, [])
        table.save(sync_to_couch=False)
        new = LookupTable.objects.get(id=table.id)
        self.assertEqual(new.fields, table.fields)
        self.assertIsNot(new.fields, table.fields)

    @generate_cases([
        # Detect incompatibilities between the JSON data stored in the
        # database and LookupTable.fields and/or TypeField type. One or more
        # of these tests will fail if the field definition changes in an
        # incompatible way.
        #
        # Do not change any of these data formats as long as rows with the
        # same format may exist in a database somewhere.
        ([],),
        ([{"name": "vera", "properties": [], "is_indexed": False}],),
        ([{"name": "vera", "properties": ["album"], "is_indexed": True}],),
    ])
    def test_persistent_formats(self, value):
        obj = LookupTable()
        set_json_value(obj, "fields", value)
        if value:
            self.assertTrue(
                all(isinstance(f, TypeField) for f in obj.fields),
                obj.fields
            )
        else:
            self.assertEqual(obj.fields, value)


class TestLookupTableRow(TestCase):

    def test_fields(self):
        table = LookupTable(domain="test", tag="x", fields=[TypeField("vera")])
        row = LookupTableRow(domain="test", table=table, fields={
            "vera": [Field("What has become of you?")],
        }, sort_key=0)
        self.assertEqual(row.fields["vera"][0].value, "What has become of you?")
        self.assertEqual(row.fields["vera"][0].properties, {})
        table.save(sync_to_couch=False)
        row.save(sync_to_couch=False)
        new = LookupTableRow.objects.get(id=row.id)
        self.assertEqual(new.fields, row.fields)
        self.assertIsNot(new.fields, row.fields)

    @generate_cases([
        # Detect incompatibilities between the JSON data stored in the
        # database and TestLookupTableRow.fields and/or Field type. One or
        # more of these tests will fail if the field definition changes in
        # an incompatible way.
        #
        # Do not change any of these data formats as long as rows with the
        # same format may exist in a database somewhere.
        ({},),
        ({"vera": []},),
        ({"vera": [{"value": "What has become of you?", "properties": {}}]},),
        ({"vera": [{
            "value": "What has become of you?",
            "properties": {"album": "The Wall"}
        }]},),
    ])
    def test_persistent_formats(self, value):  # noqa: F811
        obj = LookupTableRow()
        set_json_value(obj, "fields", value)
        if value.get("vera"):
            self.assertTrue(
                all(isinstance(f, Field) for v in obj.fields.values() for f in v),
                obj.fields
            )
        else:
            self.assertEqual(obj.fields, value)


class TestFieldTypes(SimpleTestCase):

    def test_type_field_equality(self):
        f1 = FixtureTypeField(field_name="name", properties=["a", "b"], is_indexed=True)
        f2 = FixtureTypeField(field_name="name", properties=["a", "b"], is_indexed=True)
        self.assertIsNot(f1, f2)
        self.assertEqual(f1, f2)

        f3 = FixtureTypeField(field_name="name", properties=["a"], is_indexed=True)
        self.assertNotEqual(f1, f3)
        self.assertNotEqual(f1, None)

        f4 = FixtureTypeField(field_name="name", properties=["a", "b"], is_indexed=False)
        self.assertNotEqual(f1, f4)

        f5 = FixtureTypeField(field_name="diff", properties=["a", "b"], is_indexed=True)
        self.assertNotEqual(f1, f5)

    def test_type_field_hash(self):
        f1 = FixtureTypeField(field_name="name", properties=["a", "b"], is_indexed=True)
        f2 = FixtureTypeField(field_name="name", properties=["a", "b"], is_indexed=True)
        self.assertEqual(hash(f1), hash(f2))

        f3 = FixtureTypeField(field_name="name", properties=["a"], is_indexed=True)
        self.assertNotEqual(hash(f1), hash(f3))

        f4 = FixtureTypeField(field_name="name", properties=["a", "b"], is_indexed=False)
        self.assertNotEqual(hash(f1), hash(f4))

        f5 = FixtureTypeField(field_name="diff", properties=["a", "b"], is_indexed=True)
        self.assertNotEqual(hash(f1), hash(f5))

    def test_field_equality(self):
        f1 = FixtureItemField(field_value="val", properties={"a": "1", "b": "2"})
        f2 = FixtureItemField(field_value="val", properties={"b": "2", "a": "1"})
        self.assertIsNot(f1, f2)
        self.assertEqual(f1, f2)

        f3 = FixtureItemField(field_value="val", properties={"prop": "val"})
        self.assertNotEqual(f1, f3)
        self.assertNotEqual(f1, None)

        f4 = FixtureItemField(field_value="dif", properties={"a": "1", "b": "2"})
        self.assertNotEqual(f1, f4)

    def test_field_hash(self):
        f1 = FixtureItemField(field_value="val", properties={"a": "1", "b": "2"})
        f2 = FixtureItemField(field_value="val", properties={"b": "2", "a": "1"})
        self.assertEqual(hash(f1), hash(f2))

        f3 = FixtureItemField(field_value="val", properties={"prop": "val"})
        self.assertNotEqual(hash(f1), hash(f3))

        f4 = FixtureItemField(field_value="dif", properties={"a": "1", "b": "2"})
        self.assertNotEqual(hash(f1), hash(f4))

    def test_field_list_equality(self):
        f1 = FixtureItemField(field_value="val", properties={})
        f2 = FixtureItemField(field_value="val", properties={})
        x1 = FieldList(field_list=[f1])
        x2 = FieldList(field_list=[f2])
        self.assertIsNot(x1, x2)
        self.assertEqual(x1, x2)
        self.assertEqual(hash(x1), hash(x2))

        f3 = FixtureItemField(field_value="val", properties={"prop": "val"})
        x3 = FieldList(field_list=[f3])
        self.assertNotEqual(x1, x3)
        self.assertNotEqual(x1, None)

    def test_field_list_hash(self):
        f1 = FixtureItemField(field_value="val", properties={})
        f2 = FixtureItemField(field_value="val", properties={})
        x1 = FieldList(field_list=[f1])
        x2 = FieldList(field_list=[f2])
        self.assertEqual(hash(x1), hash(x2))

        f3 = FixtureItemField(field_value="val", properties={"prop": "val"})
        x3 = FieldList(field_list=[f3])
        self.assertNotEqual(hash(x1), hash(x3))
