from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from ..management.commands.populate_lookuptables import Command as LookupTableCommand
from ..models import FixtureDataType, LookupTable, TypeField
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

    def test_diff_item_attributes(self):
        doc, obj = create_lookup_table()
        obj.item_attributes = ['age']
        self.assertEqual(
            self.diff(doc, obj),
            ["item_attributes: couch value ['name'] != sql value ['age']"],
        )

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

    def diff(self, doc, obj):
        return do_diff(LookupTableCommand, doc, obj)


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
