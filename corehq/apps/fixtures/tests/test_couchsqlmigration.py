from uuid import UUID

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from ..management.commands.populate_lookuptables import Command as LookupTableCommand
from ..management.commands.populate_lookuptablerows import Command as LookupTableRowCommand
from ..models import (
    Field,
    FixtureDataItem,
    FixtureDataType,
    LookupTable,
    LookupTableRow,
    TypeField,
)
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types


class TestLookupTableCouchToSQLDiff(SimpleTestCase):

    def test_no_diff(self):
        doc, obj = create_lookup_table()
        self.assertEqual(self.diff(doc, obj), [])

    def test_diff_domain(self):
        doc, obj = create_lookup_table()
        doc['domain'] = 'other-domain'
        self.assertEqual(
            self.diff(doc, obj),
            ["domain: couch value 'other-domain' != sql value 'some-domain'"],
        )

    def test_diff_is_global(self):
        doc, obj = create_lookup_table()
        obj.is_global = False
        self.assertEqual(
            self.diff(doc, obj),
            ["is_global: couch value True != sql value False"],
        )

    def test_diff_tag(self):
        doc, obj = create_lookup_table()
        obj.tag = 'cost'
        self.assertEqual(
            self.diff(doc, obj),
            ["tag: couch value 'price' != sql value 'cost'"],
        )

    def test_diff_fields(self):
        doc, obj = create_lookup_table()
        doc['fields'] = [{
            'doc_type': 'FixtureTypeField',
            'field_name': 'amount',
            'properties': [],
            'is_indexed': False,
        }]
        error, = self.diff(doc, obj)
        self.assertRegex(
            error,
            r"^fields: couch value \[[^q]+\] != sql value \[.+\]$",
        )

    def test_diff_old_style_fields(self):
        doc, obj = create_lookup_table()
        doc['fields'] = ['amount']
        error, = self.diff(doc, obj)
        self.assertRegex(
            error,
            r"^fields: couch value \[[^q]+\] != sql value \[.+\]$",
        )

    def test_diff_item_attributes(self):
        doc, obj = create_lookup_table()
        obj.item_attributes = ['age']
        self.assertEqual(
            self.diff(doc, obj),
            ["item_attributes: couch value ['name'] != sql value ['age']"],
        )

    def test_diff_doc_without_item_attributes(self):
        doc, obj = create_lookup_table()

        del doc["item_attributes"]
        self.assertEqual(
            self.diff(doc, obj),
            ["item_attributes: couch value None != sql value ['name']"],
        )

        obj.item_attributes = []
        self.assertEqual(self.diff(doc, obj), [])  # None in Couch == [] in SQL

    def test_diff_description(self):
        doc, obj = create_lookup_table()
        obj.description = 'about that'
        self.assertEqual(
            self.diff(doc, obj),
            ["description: couch value None != sql value 'about that'"],
        )

    def test_diff_multiple(self):
        doc, obj = create_lookup_table()
        obj.is_global = False
        doc["tag"] = 'cost'
        self.assertEqual(
            self.diff(doc, obj),
            [
                "is_global: couch value True != sql value False",
                "tag: couch value 'cost' != sql value 'price'",
            ],
        )

    def diff(self, doc, obj):
        return do_diff(LookupTableCommand, doc, obj)


class TestLookupTableRowCouchToSQLDiff(SimpleTestCase):

    def test_no_diff(self):
        doc, obj = create_lookup_table_row()
        self.assertEqual(self.diff(doc, obj), [])

    def test_diff_domain(self):
        doc, obj = create_lookup_table_row()
        doc['domain'] = 'other-domain'
        self.assertEqual(
            self.diff(doc, obj),
            ["domain: couch value 'other-domain' != sql value 'some-domain'"],
        )

    def test_diff_table_id(self):
        doc, obj = create_lookup_table_row()
        doc['data_type_id'] = couch_id = 'cddc3a035aab444a8ead069c942d7472'
        sql_id = UUID('0fb6c422115145c0a651bb9a34ca09c4')
        self.assertEqual(
            self.diff(doc, obj),
            [f"table_id: couch value {UUID(couch_id)!r} != sql value {sql_id!r}"],
        )

    def test_diff_fields(self):
        doc, obj = create_lookup_table_row()
        del doc['fields']['qty']
        error, = self.diff(doc, obj)
        self.assertRegex(
            error,
            r"^fields: couch value \{[^qy]+\} != sql value \{.+\}$",
        )

    def test_diff_old_style_fields(self):
        doc, obj = create_lookup_table_row()
        doc['fields'] = {'amount': '1'}
        error, = self.diff(doc, obj)
        self.assertRegex(
            error,
            r"^fields: couch value \{[^qy]+\} != sql value \{.+\}$",
        )

    def test_diff_item_attributes(self):
        doc, obj = create_lookup_table_row()
        obj.item_attributes = {'age': '4'}
        self.assertEqual(
            self.diff(doc, obj),
            ["item_attributes: couch value {'name': 'Andy'} != sql value {'age': '4'}"],
        )

    def test_diff_doc_without_item_attributes(self):
        doc, obj = create_lookup_table_row()

        del doc["item_attributes"]
        self.assertEqual(
            self.diff(doc, obj),
            ["item_attributes: couch value {} != sql value {'name': 'Andy'}"],
        )

        obj.item_attributes = {}
        self.assertEqual(self.diff(doc, obj), [])  # not in Couch == {} in SQL

    def test_diff_sort_key(self):
        doc, obj = create_lookup_table_row()
        obj.sort_key = 25
        self.assertEqual(
            self.diff(doc, obj),
            ["sort_key: couch value 2 != sql value 25"],
        )

    def test_diff_null_sort_key(self):
        doc, obj = create_lookup_table_row()
        doc["sort_key"] = None
        obj.sort_key = 0
        self.assertEqual(self.diff(doc, obj), [])

    def test_diff_multiple(self):
        doc, obj = create_lookup_table_row()
        obj.sort_key = 25
        doc["data_type_id"] = couch_id = 'cddc3a035aab444a8ead069c942d7472'
        sql_id = UUID('0fb6c422115145c0a651bb9a34ca09c4')
        self.assertEqual(
            self.diff(doc, obj),
            [
                f"table_id: couch value {UUID(couch_id)!r} != sql value {sql_id!r}",
                "sort_key: couch value 2 != sql value 25",
            ],
        )

    def diff(self, doc, obj):
        return do_diff(LookupTableRowCommand, doc, obj)


class TestLookupTableCouchToSQLMigration(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = FixtureDataType.get_db()

    def tearDown(self):
        docs = list(get_all_docs_with_doc_types(self.db, ['FixtureDataType']))
        self.db.bulk_delete(docs)
        super().tearDown()

    def test_sync_to_couch(self):
        doc, obj = create_lookup_table()
        obj.save()
        couch_obj = self.db.get(obj._migration_couch_id)
        self.assertIsNone(couch_obj['description'], None)
        self.assertEqual(self.diff(couch_obj, obj), [])

        obj.tag = 'cost'
        obj.fields[0].name = 'value'
        obj.item_attributes = ['name', 'age']
        obj.description = 'about that'
        obj.save()
        doc = self.db.get(obj._migration_couch_id)
        self.assertEqual(doc['tag'], 'cost')
        self.assertEqual(doc['description'], 'about that')
        self.assertEqual(doc['item_attributes'], ['name', 'age'])
        self.assertEqual(doc['fields'][0], {
            'doc_type': 'FixtureTypeField',
            'field_name': 'value',
            'properties': [],
            'is_indexed': False,
        })

    def test_sync_to_sql(self):
        doc, obj = create_lookup_table(unwrap_doc=False)
        doc.save()
        self.assertEqual(
            self.diff(doc.to_json(), LookupTable.objects.get(id=doc._id)),
            [],
        )

        doc.tag = 'cost'
        doc.fields[0].field_name = 'value'
        doc.item_attributes = ['name', 'age']
        doc.save()
        obj = LookupTable.objects.get(id=doc._id)
        self.assertEqual(obj.tag, 'cost')
        self.assertEqual(obj.item_attributes, ['name', 'age'])
        self.assertEqual(obj.fields[0], TypeField(
            name='value',
            properties=[],
            is_indexed=False,
        ))

    def test_migration(self):
        doc, obj = create_lookup_table(unwrap_doc=False)
        doc.save(sync_to_sql=False)
        call_command('populate_lookuptables')
        self.assertEqual(
            self.diff(doc.to_json(), LookupTable.objects.get(id=doc._id)),
            [],
        )

        # Additional call should apply any updates
        doc = FixtureDataType.get(doc._id)
        doc.tag = 'cost'
        doc.fields[0].field_name = 'value'
        doc.item_attributes = ['name', 'age']
        doc.save(sync_to_sql=False)
        call_command('populate_lookuptables')
        self.assertEqual(
            self.diff(doc.to_json(), LookupTable.objects.get(id=doc._id)),
            [],
        )

    def test_migration_with_old_doc_format(self):
        doc, obj = create_lookup_table()
        doc['fields'] = ['amount', 'qty']
        del doc['item_attributes']
        self.db.save_doc(doc)
        call_command('populate_lookuptables')
        self.assertEqual(
            self.diff(doc, LookupTable.objects.get(id=doc['_id'])),
            [],
        )

        # Additional call should apply any updates
        doc['tag'] = 'cost'
        doc['fields'] = ['value', 'qty']
        assert 'item_attributes' not in doc, doc
        self.db.save_doc(doc)
        call_command('populate_lookuptables')
        self.assertEqual(
            self.diff(doc, LookupTable.objects.get(id=doc['_id'])),
            [],
        )

    def diff(self, doc, obj):
        return do_diff(LookupTableCommand, doc, obj)


class TestLookupTableRowCouchToSQLMigration(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = FixtureDataItem.get_db()
        cls.type_doc = create_lookup_table(unwrap_doc=False)[0]
        cls.type_doc.save()
        cls.table_obj = LookupTable.objects.get(id=cls.type_doc._id)
        cls.addClassCleanup(cls.type_doc.delete)

    def tearDown(self):
        docs = list(get_all_docs_with_doc_types(self.db, ['FixtureDataItem']))
        self.db.bulk_delete(docs)
        super().tearDown()

    def test_sync_to_couch(self):
        doc, obj = self.create_row()
        obj.save()
        self.assertEqual(self.diff(self.db.get(obj._migration_couch_id), obj), [])

        obj.fields['amount'][0].value = '42'
        obj.item_attributes = {'name': 'Andy', 'age': '4'}
        obj.sort_key = -1
        obj.save()
        doc = self.db.get(obj._migration_couch_id)
        self.assertEqual(doc['item_attributes'], {'name': 'Andy', 'age': '4'})
        self.assertEqual(doc['fields']['amount']['field_list'][0], {
            'doc_type': 'FixtureItemField',
            'field_value': '42',
            'properties': {},
        })
        self.assertEqual(doc['sort_key'], -1)

    def test_sync_to_sql(self):
        doc, obj = self.create_row()
        doc.save()
        self.assertEqual(
            self.diff(doc.to_json(), LookupTableRow.objects.get(id=UUID(doc._id))),
            [],
        )

        doc.fields['amount']['field_list'][0]['field_value'] = '1000'
        doc.item_attributes = {'name': 'Andy', 'age': '4'}
        doc.sort_key = None
        doc.save()
        obj = LookupTableRow.objects.get(id=UUID(doc._id))
        self.assertEqual(obj.item_attributes, {'name': 'Andy', 'age': '4'})
        self.assertEqual(obj.fields['amount'], [Field('1000', {})])
        self.assertEqual(obj.sort_key, 0)

    def test_migration(self):
        doc, obj = self.create_row()
        doc.save(sync_to_sql=False)
        call_command('populate_lookuptablerows')
        self.assertEqual(
            self.diff(doc.to_json(), LookupTableRow.objects.get(id=UUID(doc._id))),
            [],
        )

        # Additional call should apply any updates
        doc = FixtureDataItem.get(doc._id)
        doc.fields['amount']['field_list'][0]['field_value'] = '1000'
        doc.item_attributes = {'name': 'Andy', 'age': '4'}
        doc.sort_key = None
        doc.save(sync_to_sql=False)
        call_command('populate_lookuptablerows')
        self.assertEqual(
            self.diff(doc.to_json(), LookupTableRow.objects.get(id=UUID(doc._id))),
            [],
        )

    def test_migration_with_old_doc_format(self):
        doc, obj = self.create_row()
        data = doc.to_json()
        data['fields'] = {'amount': 1}  # old format
        del data['item_attributes']
        doc_id = self.db.save_doc(data)["id"]
        call_command('populate_lookuptablerows')
        doc_json = {
            **data,
            '_id': doc_id,
            'fields': {  # new format
                'amount': {'doc_type': 'FieldList', 'field_list': [
                    {
                        'field_value': '1',
                        'properties': {},
                        'doc_type': 'FixtureItemField',
                    }
                ]}
            },
            'item_attributes': {},
        }
        self.assertEqual(
            self.diff(doc_json, LookupTableRow.objects.get(id=UUID(doc_id))),
            [],
        )

    def create_row(self):
        doc, obj = create_lookup_table_row(unwrap_doc=False)
        doc.data_type_id = self.type_doc._id
        obj.table = self.table_obj
        assert obj.table_id == self.table_obj.id, (obj.table_id, self.table_obj.id)
        return doc, obj

    def diff(self, doc, obj):
        return do_diff(LookupTableRowCommand, doc, obj)


def create_lookup_table(unwrap_doc=True):
    def fields_data(name="name"):
        return [
            {
                name: 'amount',
                'properties': [],
                'is_indexed': False,
            }, {
                name: 'qty',
                'properties': [],
                'is_indexed': False,
            },
        ]

    def data(**extra):
        return {
            'domain': 'some-domain',
            'is_global': True,
            'tag': 'price',
            'fields': fields_data(),
            'item_attributes': ['name'],
            **extra,
        }
    obj = jsonattrify(LookupTable, data())
    doc = FixtureDataType.wrap(data(
        doc_type="FixtureDataType",
        fields=fields_data("field_name"),
    ))
    if unwrap_doc:
        doc = doc.to_json()
    return doc, obj


def create_lookup_table_row(unwrap_doc=True):
    def data(**extra):
        return {
            'domain': 'some-domain',
            'item_attributes': {'name': 'Andy'},
            'sort_key': 2,
            **extra,
        }
    obj = jsonattrify(LookupTableRow, data(
        table_id=UUID('0fb6c422115145c0a651bb9a34ca09c4'),
        fields={
            'amount': [
                {"value": "1", "properties": {}},
            ],
            'qty': [
                {"value": "1", "properties": {"loc": "Boston"}},
                {"value": "3", "properties": {"loc": "Miami"}},
            ],
        },
    ))
    doc = FixtureDataItem.wrap(data(
        doc_type="FixtureDataItem",
        data_type_id="0fb6c422115145c0a651bb9a34ca09c4",
        fields={
            'amount': {'field_list': [
                {"field_value": "1", "properties": {}},
            ]},
            'qty': {'field_list': [
                {"field_value": "1", "properties": {"loc": "Boston"}},
                {"field_value": "3", "properties": {"loc": "Miami"}},
            ]},
        },
    ))
    if unwrap_doc:
        doc = doc.to_json()
    return doc, obj


def do_diff(Command, doc, obj):
    result = Command.diff_couch_and_sql(doc, obj)
    return [x for x in result if x is not None]


def jsonattrify(model_type, data):
    obj = model_type()
    for name, value in data.items():
        field = model_type._meta.get_field(name)
        if hasattr(field, "builder"):
            value = field.builder.attrify(value)
        setattr(obj, name, value)
    return obj
