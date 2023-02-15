from uuid import UUID
from operator import attrgetter

from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.models import Domain
from corehq.util.test_utils import generate_cases
from corehq.util.tests.test_jsonattrs import set_json_value

from ..models import (
    Field,
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
        table.save()


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
        table.save()
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
        cls.table = LookupTable(
            domain=cls.domain.name,
            tag="pink",
            fields=[TypeField("vera")],
        )
        cls.table.save()

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

    def test_iter_rows_with_tag(self):
        self.create_rows(7)
        rows = list(LookupTableRow.objects.iter_rows(self.domain.name, tag="pink"))
        self.assertEqual(
            [r.fields["num"][0].value for r in rows],
            [str(x) for x in range(7)],
        )

    def test_iter_rows_with_tag_and_unknown_domain(self):
        self.create_rows(1)
        rows = list(LookupTableRow.objects.iter_rows("unknown", tag="pink"))
        self.assertEqual(rows, [])

    def test_iter_rows_too_many_args(self):
        with self.assertRaisesRegex(TypeError, "Too many arguments"):
            LookupTableRow.objects.iter_rows("x", table_id="y", tag="z")

    def test_iter_rows_not_enough_args(self):
        with self.assertRaisesRegex(TypeError, "Not enough arguments"):
            LookupTableRow.objects.iter_rows("x")

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

    def test_iter_by_user_with_multiple_tables(self):
        class bob:
            domain = self.domain.name
            user_id = "bob"
            sql_location = None
        self.maxDiff = None

        # create tables with ids indexed off of "pink" self.table.id
        blue_table = LookupTable(
            id=UUID(int=self.table.id.int - 1),
            domain=self.domain.name,
            tag="blue",
        )
        red_table = LookupTable(
            id=UUID(int=self.table.id.int + 1),
            domain=self.domain.name,
            tag="red",
        )
        LookupTable.objects.bulk_create([red_table, blue_table])

        pink_rows = self.create_rows(10, sort_key=10)

        # create row with lower table_id, lower id, and equal sort_key to pink_rows
        # requires table_id in
        #   Q(table_id=row.table_id, sort_key=row.sort_key, id__gt=row.id)
        blue_row = LookupTableRow(
            id=UUID(int=max(p.id for p in pink_rows).int + 1),
            domain=self.domain.name,
            table=blue_table,
            sort_key=10,
        )
        blue_row.save()

        # create rows with higher table_id and lower sort_key than pink_rows
        # requires table_id in
        #   Q(table_id=row.table_id, sort_key__gt=row.sort_key)
        #   and
        #   Q(table_id__gt=row.table_id)
        red_rows = self.create_rows(10, table=red_table, sort_key=5)

        self.add_owner(bob, [blue_row] + red_rows + pink_rows)
        ident = attrgetter("id")
        tags = {t.id: t.tag for t in [self.table, red_table, blue_table]}

        # 21 rows -> 8 queries: 7 batches of size 3 + 1 extra query
        with self.assertNumQueries(8):
            rows = list(LookupTableRow.objects.iter_by_user(bob, batch_size=3))
            self.assertEqual(
                [(tags[r.table_id], r.id) for r in rows],
                [('blue', blue_row.id)]
                + [('pink', e.id) for e in sorted(pink_rows, key=ident)]
                + [('red', d.id) for d in sorted(red_rows, key=ident)],
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

    def test_with_value(self):
        self.create_rows(2)
        row = LookupTableRow.objects.with_value(self.domain.name, self.table.id, "num", "1").get()
        self.assertEqual(row.fields["num"][0].value, "1")

    def test_with_value_not_first_value(self):
        self.create_rows(2, get_fields=lambda i: [Field(value=str(i)), Field(value="10")])
        rows = LookupTableRow.objects.with_value(self.domain.name, self.table.id, "num", "10")
        self.assertEqual({r.fields["num"][0].value for r in rows}, {"0", "1"})
        self.assertEqual({r.fields["num"][1].value for r in rows}, {"10"})
        self.assertEqual({r.sort_key for r in rows}, {0, 1})

    def test_with_value_with_duplicate_values(self):
        self.create_rows(1, get_fields=lambda i: [Field(value="10"), Field(value="10")])
        rows = LookupTableRow.objects.with_value(self.domain.name, self.table.id, "num", "10")
        self.assertEqual(rows.count(), 1)

    def create_rows(self, count,
                    table=None, sort_key=None,
                    get_fields=lambda i: [Field(value=str(i))]):
        rows = [LookupTableRow(
            domain=self.domain.name,
            table=(table or self.table),
            fields={"num": get_fields(index)},
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
        row.table.save()
        row.save()
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
            row.table.save()
            row.save()
        return row


class TestFieldTypes(SimpleTestCase):

    def test_type_field_equality(self):
        f1 = TypeField(name="name", properties=["a", "b"], is_indexed=True)
        f2 = TypeField(name="name", properties=["a", "b"], is_indexed=True)
        self.assertIsNot(f1, f2)
        self.assertEqual(f1, f2)

        f3 = TypeField(name="name", properties=["a"], is_indexed=True)
        self.assertNotEqual(f1, f3)
        self.assertNotEqual(f1, None)

        f4 = TypeField(name="name", properties=["a", "b"], is_indexed=False)
        self.assertNotEqual(f1, f4)

        f5 = TypeField(name="diff", properties=["a", "b"], is_indexed=True)
        self.assertNotEqual(f1, f5)

    def test_type_field_hash(self):
        f1 = TypeField(name="name", properties=["a", "b"], is_indexed=True)
        f2 = TypeField(name="name", properties=["a", "b"], is_indexed=True)
        self.assertEqual(hash(f1), hash(f2))

        f3 = TypeField(name="name", properties=["a"], is_indexed=True)
        self.assertNotEqual(hash(f1), hash(f3))

        f4 = TypeField(name="name", properties=["a", "b"], is_indexed=False)
        self.assertNotEqual(hash(f1), hash(f4))

        f5 = TypeField(name="diff", properties=["a", "b"], is_indexed=True)
        self.assertNotEqual(hash(f1), hash(f5))

    def test_field_equality(self):
        f1 = Field(value="val", properties={"a": "1", "b": "2"})
        f2 = Field(value="val", properties={"b": "2", "a": "1"})
        self.assertIsNot(f1, f2)
        self.assertEqual(f1, f2)

        f3 = Field(value="val", properties={"prop": "val"})
        self.assertNotEqual(f1, f3)
        self.assertNotEqual(f1, None)

        f4 = Field(value="dif", properties={"a": "1", "b": "2"})
        self.assertNotEqual(f1, f4)

    def test_field_hash(self):
        f1 = Field(value="val", properties={"a": "1", "b": "2"})
        f2 = Field(value="val", properties={"b": "2", "a": "1"})
        self.assertEqual(hash(f1), hash(f2))

        f3 = Field(value="val", properties={"prop": "val"})
        self.assertNotEqual(hash(f1), hash(f3))

        f4 = Field(value="dif", properties={"a": "1", "b": "2"})
        self.assertNotEqual(hash(f1), hash(f4))
