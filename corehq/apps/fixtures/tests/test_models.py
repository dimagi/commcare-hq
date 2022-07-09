from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.models import Domain
from corehq.util.test_utils import generate_cases
from corehq.util.tests.test_jsonattrs import set_json_value

from ..models import (
    Field,
    FieldList,
    FixtureItemField,
    FixtureTypeField,
    LookupTable,
    LookupTableRow,
    LookupTableRowOwner,
    OwnerType,
    TypeField,
)


class TestLookupTableManager(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = Domain.get_or_create_with_name("lookup-table-domain", is_active=True)
        cls.addClassCleanup(cls.domain.delete)

    def test_by_domain(self):
        tables = LookupTable.objects.by_domain(self.domain)
        self.assertFalse(tables.count())
        self.make_table()
        self.assertEqual([t.tag for t in tables], ['price'])

    def test_by_domain_tag(self):
        self.make_table()
        table = LookupTable.objects.by_domain_tag(self.domain.name, "price")
        self.assertEqual(table.tag, "price")

    def test_by_domain_tag_missing(self):
        with self.assertRaises(LookupTable.DoesNotExist):
            LookupTable.objects.by_domain_tag(self.domain.name, "lostnotfound")

    def test_domain_tag_exists(self):
        self.make_table()
        self.assertTrue(LookupTable.objects.domain_tag_exists(self.domain.name, "price"))
        self.assertFalse(LookupTable.objects.domain_tag_exists(self.domain.name, "404"))

    def make_table(self):
        table = LookupTable(
            domain=self.domain.name,
            is_global=True,
            tag='price',
            fields=[],
            item_attributes=[],
        )
        table.save(sync_to_couch=False)


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


class TestLookupTableRowManager(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = Domain.get_or_create_with_name("lookup-table-domain", is_active=True)
        cls.addClassCleanup(cls.domain.delete)
        cls.table = LookupTable(fields=[TypeField("vera")])
        cls.table.save(sync_to_couch=False)

    def test_iter_rows(self):
        self.create_rows(10)
        with self.assertNumQueries(4):
            rows = list(LookupTableRow.objects.iter_rows(
                self.domain.name, table_id=self.table.id, batch_size=3))
            self.assertEqual(
                [r.fields["num"][0].value for r in rows],
                [str(x) for x in range(10)],
            )

    def test_iter_rows_with_duplicate_sort_keys(self):
        created = self.create_rows(10, sort_key=0)
        expected = sorted(created, key=lambda r: r.id)

        rows = list(LookupTableRow.objects.iter_rows(
            self.domain.name, table_id=self.table.id, batch_size=3))
        self.assertEqual(
            [r.fields["num"][0].value for r in rows],
            [r.fields["num"][0].value for r in expected],
        )

    def test_iter_by_user(self):
        class bob:
            domain = self.domain.name
            user_id = "bob"
            sql_location = None
        created = self.create_rows(20)
        even_rows = [created[i] for i in range(0, 20, 2)]
        self.add_owner(bob, even_rows)
        with self.assertNumQueries(4):
            rows = list(LookupTableRow.objects.iter_by_user(bob, batch_size=3))
            self.assertEqual(
                [r.fields["num"][0].value for r in rows],
                [str(x) for x in range(0, 20, 2)],
            )

    def test_iter_by_user_with_duplicate_sort_keys(self):
        class bob:
            domain = self.domain.name
            user_id = "bob"
            sql_location = None
        created = self.create_rows(20, sort_key=0)
        even_rows = [created[i] for i in range(0, 20, 2)]
        expected = sorted(even_rows, key=lambda r: r.id)
        self.add_owner(bob, even_rows)

        rows = list(LookupTableRow.objects.iter_by_user(bob, batch_size=3))
        nums = [r.fields["num"][0].value for r in rows]
        self.assertEqual(nums, [r.fields["num"][0].value for r in expected])
        self.assertEqual(len(rows), 10, nums)

    def create_rows(self, count, sort_key=None):
        rows = [LookupTableRow(
            domain=self.domain.name,
            table=self.table,
            fields={"num": [Field(value=str(index))]},
            sort_key=index if sort_key is None else sort_key,
        ) for index in range(count)]
        LookupTableRow.objects.bulk_create(rows)
        return rows

    def add_owner(self, user, rows):
        owners = [LookupTableRowOwner(
            domain=self.domain.name,
            row_id=row.id,
            owner_type=OwnerType.User,
            owner_id=user.user_id,
        ) for row in rows]
        LookupTableRowOwner.objects.bulk_create(owners)


class TestLookupTableRow(TestCase):

    def test_fields(self):
        row = self.make_row(save=False)
        self.assertEqual(row.fields["vera"][0].value, "What has become of you?")
        self.assertEqual(row.fields["vera"][0].properties, {})
        row.table.save(sync_to_couch=False)
        row.save(sync_to_couch=False)
        new = LookupTableRow.objects.get(id=row.id)
        self.assertEqual(new.fields, row.fields)
        self.assertIsNot(new.fields, row.fields)

    def test_on_delete_cascade(self):
        row = self.make_row()
        table = row.table
        # Django's implementation of cascading deletes does 5 queries
        #with self.assertNumQueries(1):
        LookupTable.objects.filter(domain=table.domain, tag=table.tag).delete()
        with self.assertRaises(LookupTableRow.DoesNotExist):
            LookupTableRow.objects.get(id=row.id)

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

    def make_row(self, save=True):
        table = LookupTable(domain="test", tag="x", fields=[TypeField("vera")])
        row = LookupTableRow(domain="test", table=table, fields={
            "vera": [Field("What has become of you?")],
        }, sort_key=0)
        if save:
            row.table.save(sync_to_couch=False)
            row.save(sync_to_couch=False)
        return row


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
