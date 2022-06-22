from django.test import SimpleTestCase

from ..models import FieldList, FixtureItemField, FixtureTypeField


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
